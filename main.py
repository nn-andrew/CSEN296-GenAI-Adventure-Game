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

def generate_prompt_from_user_input():
    description = input("Describe the point-and-click adventure: ")
    # prompt = f"Your response should follow the following format, and nothing else should be in your response: '[object1],[object2],[object3],[object4],[object5]'. In that format, list the 5 most important objects to depict this scene: {description}"
    return """You will be given a description of a point-and-click adventure game. Based on that description, generate a structured JSON object that includes:

    1. **Three interactable objects**, each with:
    - A name
    - A description
    - A list of allowed interaction_names (from: "Talk")
    - An explanation of how the object helps solve a puzzle (if it does)

    2. **Two detailed scene prompts that relate to the provided description** suitable for use with SD3 image generation.

    The JSON format must match this structure:
    ```json {{
        "scenes": {{
            "scene_name1": {{
                "scene_description": "Text-to-image prompt for SD3 scene 1",
                "items": [
                    {{
                        "name": "item1",
                        "description": "Description of item1",
                        "allowed_interactions": {{
                            "talk": "Dialogue for item1"
                        }}
                    }},
                    {{
                        "name": "item2",
                        "description": "Description of item2",
                        "allowed_interactions": {{
                            "talk": "Dialogue for item2"
                        }}
                    }}
                ]
            }},
            "scene_name2": {{
                "scene_description": "Text-to-image prompt for SD3 scene 2",
                "items": [
                    {{
                        "name": "item3",
                        "description": "Description of item3",
                        "allowed_interactions": {{
                            "talk": "Dialogue for item3"
                        }}
                    }}
                ]
            }},
        }}
    }}

    Description: {}

    Now generate the JSON output. Don't say anything else.
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
    
    scene_prompt = f"Game pixel art VGA 90’s style (like secret of monkey island). {scene_description}, with several items: {', '.join(scene_items)}"
    output_filename = f"scene_{scene_name}"
    filenames.append(output_filename)

    call_sd3(scene_prompt, output_filename=output_filename)

    for item_name in scene_items:
        item_prompt = f"Game pixel art VGA 90’s style (like secret of monkey island). {item_name}, plain black background"
        output_filename = f"icon_{item_name.replace(' ', '_')}"

        call_sd3(item_prompt, output_filename=output_filename)

        filenames.append(output_filename)

    return filenames

@my_vcr.use_cassette('fixtures/vcr_cassettes/openai.yaml', match_on=['method', 'uri', 'text_only'], record_mode=RECORD_MODE)
def call_openai(image_filename_without_extension, prompt):
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
    
    return call_openai(image_filename, prompt)

# *** STEP 1 ***
# night time jazz lounge
prompt = generate_prompt_from_user_input()

ollama_response_str = call_ollama(prompt)
ollama_response_json = json.loads(ollama_response_str)

# Parse scenes from JSON response
scenes = ollama_response_json["scenes"]
scene_names = []
i = 0
limit = 2
for scene_name in ollama_response_json["scenes"]:
    if i >= limit:
        break
    scene_names.append(scene_name)
    i += 1

# # *** STEP 2 ***
# # call_sdxl(scenes)
# # call_sdxl(icons, category="icon", height=512, width=512, num_inference_steps=25)
all_item_names = []
scene_to_items: Dict[str, Dict[str, Tuple[float, float]]] = {} # {scene_name: {item_name: (x, y)}}
for scene_name in scene_names:
    item_names = [item["name"] for item in scenes[scene_name]["items"]]
    all_item_names.extend(item_names)

    scene_description = scenes[scene_name]["scene_description"]

    filenames = generate_images_for_scene_and_icons(scene_name, scene_description, item_names)
    scene_filename = filenames[0]
    
    ''' e.g.
    item1_name,0.5,0.5
    item2_name,0.3,0.7
    '''
    item_coords_str = get_item_coordinates_in_image(scene_filename, item_names)
    print(item_coords_str)
    scene_to_items[scene_name] = {}
    for line in item_coords_str.splitlines():
        parts = line.strip().split(',')
        if len(parts) == 3:
            item_name = parts[0].strip()
            x = float(parts[1].strip())
            y = float(parts[2].strip())
            
            scene_to_items[scene_name][item_name] = (x, y)
