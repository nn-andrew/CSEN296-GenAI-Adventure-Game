import argparse
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests
import json
# from diffusers import DiffusionPipeline
# import torch
import openai
import base64
from typing import Dict, Tuple

import vcr
import re
from functools import lru_cache

from dotenv import load_dotenv
import os
load_dotenv()

# TODO: Function not needed anymore, can use match_text_only() to compare responses instead
@lru_cache(maxsize=None)
def get_base64_image(image_path):
    with open(image_path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")
    
my_vcr = vcr.VCR()
def match_text_only(r1, r2):
    try:
        b1 = json.loads(r1.body)
        b2 = json.loads(r2.body)

        def extract_text(msg_list):
            return [entry["text"] for m in msg_list for entry in m["content"] if entry["type"] == "text"]

        text1 = extract_text(b1["messages"])
        text2 = extract_text(b2["messages"])

        return text1 == text2
    except Exception:
        return False

def normalize_multipart(body_bytes):
    # Decode bytes safely
    body = body_bytes.decode('utf-8', errors='ignore')
    
    # Strip dynamic boundary lines
    # Replace boundary markers like: --{boundary}\r\n
    body = re.sub(r"--[a-f0-9]{32,}(\r\n|\n)?", "--<boundary>\n", body)
    
    # Remove Content-Disposition lines
    body = re.sub(r"Content-Disposition:.*?\r?\n", "", body, flags=re.IGNORECASE)
    
    # Remove any remaining headers inside the parts
    body = re.sub(r"Content-Type:.*?\r?\n", "", body, flags=re.IGNORECASE)

    # Remove any empty lines and normalize whitespace
    body = "\n".join(line.strip() for line in body.strip().splitlines() if line.strip())

    return body

def multipart_body_matcher(r1, r2):
    try:
        b1 = normalize_multipart(r1.body)
        b2 = normalize_multipart(r2.body)
        return b1 == b2
    except Exception:
        return False

my_vcr.register_matcher('text_only', match_text_only)
my_vcr.register_matcher("clean_multipart", multipart_body_matcher)

RECORD_MODE = "new_episodes"
SD3_API_KEY = os.getenv("SD3_API_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# # Load local SDXL model
# pipe = DiffusionPipeline.from_pretrained(
#     "stabilityai/stable-diffusion-xl-base-1.0",
#     torch_dtype=torch.float32
# ).to("mps")

# def call_sdxl(prompts, height=512, width=512, num_inference_steps=25, category="scene"):
#     # prompts = [
#     #     "hotel room, evening, point-and-click adventure scene, with several doorways",
#     #     "hotel bathroom with green ceramic tiles, wide shot, point-and-click adventure scene, with mirror and sink with items on the sink"
#     # ]

#     images = pipe(prompts, height=height, width=width, num_inference_steps=num_inference_steps).images

#     # Generate the image
#     # image = pipe(prompt).images[0]

#     # Show or save the image
#     for i in range(len(images)):
#         print(prompts[i])
#         image = images[i]
#         image.show()
#         image.save(f"{category}{i}.png")

@my_vcr.use_cassette('fixtures/vcr_cassettes/ollama.yaml', match_on=['method', 'uri', 'body'], record_mode=RECORD_MODE)
def call_ollama(prompt):
    headers = {"Content-Type": "application/json"}
    response = requests.post(
        "http://localhost:11434/api/generate",
        headers=headers,
        data=json.dumps({
            "model": "llama3:8b",
            "prompt": prompt,
            "stream": False
        })
    )

    if response.status_code == 200:
        response_text = response.text
        data = json.loads(response_text)
        actual_response = data['response']

        return actual_response

    return "Error: " + str(response.status_code) + " " + response.text

def generate_prompt_from_description(description):
    # prompt = f"Your response should follow the following format, and nothing else should be in your response: '[object1],[object2],[object3],[object4],[object5]'. In that format, list the 5 most important objects to depict this scene: {description}"
    return """You will be given a description of a point-and-click adventure game. Based on that description, generate a structured JSON object that includes:

    1. Two scenes, each with:
    - scene_description: a detailed prompt suitable for SD3 image generation.
    - items: a dictionary where each key is the item name. one of the items has to be a path to the other scene (for example a door or walkway or alley)
    - description: should be short with some light humor, 8 words or less
    - interactions: a dictionary where keys are interaction types (e.g., "talk", "use", "look", "pick up") and values are the corresponding dialogue or behavior
    - the name of the starting scene should be prefixed with "START_"

    2. A single puzzle, with:
    - id: a unique identifier like "puzzle_1"
    - type: one of "item_combination", "item_usage", "dialog", or "environment"
    - description: a short summary of the puzzle
    - requirements: item(s), interaction(s), or conditions required to solve the puzzle.
    - result: must be exactly:
    "result": {{
        "unlocked_area": {{name of scene unlocked}}
    }}
    
    The puzzle always results in unlocking the second scene.

    The output must exactly match this format:

    {{
    "scenes": {{
        {{scene_name}}: {{
            "scene_description": {{Descriptive text-to-image prompt for this scene for SD3}},
            "items": {{
                {{item_name}}: {{
                    "description": {{Short humorous description}},
                    "interactions": {{
                        {{usage_type}}: {{dialogue after performing the interaction}}
                    }}
                }}
            }}
        }},
    }},
    "puzzles": [
        {{
            "id": {{puzzle_id}},
            "type": {{usage_type}},
            "description": {{Clue for the puzzle, 8 words or less}},
            "completion_text: "{{Text to display when the puzzle is solved, 8 words or less}}",
            "requirements": [
                [{{usage_type}}, {{item_name}}],
            ],
            "result": {{
                "unlocked_area": {{scene_name}}
            }}
        }}
    ]
    }}

    Description: {}
    Now generate the JSON output. Do not add any other text.
    """.format(description)

@my_vcr.use_cassette('fixtures/vcr_cassettes/sd3.yaml', match_on=['method', 'uri', 'clean_multipart'], record_mode=RECORD_MODE)
def call_sd3(prompt, output_filename="sd3_output"):
    # prompt = f"Game pixel art VGA 90’s style (like secret of monkey island). in line for the Indiana jones ride at disneyland, with several items: apple, dole whip, star wand, red carpet"

    response = requests.post(
        f"https://api.stability.ai/v2beta/stable-image/generate/sd3",
        headers={
            "authorization": f"Bearer {SD3_API_KEY}",
            "accept": "image/*"
        },
        files={"none": ''},
        data={
            "prompt": prompt,
            "output_format": "jpeg",
        },
    )

    if response.status_code == 200:
        with open(f"./{output_filename}.jpeg", 'wb') as file:
            file.write(response.content)
    else:
        raise Exception(str(response.json()))
    
def generate_images_for_scene_and_icons(scene_name, scene_description, scene_items):
    filenames = []
    
    scene_prompt = f"Game pixel art VGA 90’s style (like secret of monkey island). {scene_description}. The following items are clearly visible: {', '.join(scene_items)}"
    output_filename = f"scene_{scene_name}"
    filenames.append(output_filename)

    call_sd3(scene_prompt, output_filename=output_filename)

    for item_name in scene_items:
        item_prompt = f"Game pixel art VGA 90’s style (like secret of monkey island). {item_name}, plain black background"
        output_filename = f"icon_{item_name.replace(' ', '_')}"

        call_sd3(item_prompt, output_filename=output_filename)

        filenames.append(output_filename)

    return filenames

@my_vcr.use_cassette('fixtures/vcr_cassettes/openai.yaml', match_on=['method', 'uri', 'body'], record_mode=RECORD_MODE)
def call_openai(prompt):
    client = openai.OpenAI(api_key=OPENAI_API_KEY)
    
    response = client.chat.completions.create(
        model="gpt-4",
        messages=[
            {"role": "user", "content": prompt}
        ]
    )

    return response.choices[0].message.content

@my_vcr.use_cassette('fixtures/vcr_cassettes/openai.yaml', match_on=['method', 'uri', 'text_only'], record_mode=RECORD_MODE)
def call_openai_with_image(image_filename_without_extension, prompt):
    client = openai.OpenAI(api_key=OPENAI_API_KEY)

    full_image_path = f"./{image_filename_without_extension}.jpeg"

    if not os.path.exists(full_image_path):
        print(f"ERROR: Image file not found at {full_image_path} for OpenAI call.")
        return "Error: Image file not found."

    base64_image_data = get_base64_image(full_image_path)
    
    image_data_url = f"data:image/jpeg;base64,{base64_image_data}"

    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": image_data_url
                        }
                    }
                ]
            }
        ]
    )

    return response.choices[0].message.content

def get_item_coordinates_in_image(image_filename, item_names):
    prompt = f"in terms of distance ratio between left and right, top and bottom of the image (starting from left and top), where are the following items? (Format your response as lines of object_name,x,y and nothing else in your response. For example, object1_name,0.5,0.5\nobject2_name,0.5,0.5) Items: {','.join(item_names)}"
    
    return call_openai_with_image(image_filename, prompt)

def main():
    parser = argparse.ArgumentParser(
        description="Generate game_data.json + images for PnC adventure."
    )
    parser.add_argument(
        "--desc",
        type=str,
        help="A short text description of your scene"
    )
    args = parser.parse_args()

    # read from --desc or stdin
    if args.desc:
        desc = args.desc
    else:
        desc = sys.stdin.read().strip()

    prompt = generate_prompt_from_description(desc)
    openai_response_str = call_openai(prompt)
    game_data = json.loads(openai_response_str)

    scenes = list(game_data["scenes"].items())
    for scene_name, info in scenes:
        item_names = list(info["items"].keys())
        filenames = generate_images_for_scene_and_icons(
            scene_name, info["scene_description"], item_names
        )

        scene_filename = filenames[0]
        item_coords_str = get_item_coordinates_in_image(scene_filename, item_names)
        # scene_to_items[scene_name] = {}
        for line in item_coords_str.splitlines():
            parts = line.strip().split(',')
            if len(parts) == 3:
                item_name = parts[0].strip()
                x = float(parts[1].strip())
                y = float(parts[2].strip())
                
                game_data["scenes"][scene_name]["items"][item_name]["coordinates"] = (x, y)

                # scene_to_items[scene_name][item_name] = (x, y)


    # write out enriched JSON (with coordinates already injected)
    with open("game_data.json", "w") as f:
        json.dump(game_data, f, indent=2)

if __name__ == "__main__":
    main()
