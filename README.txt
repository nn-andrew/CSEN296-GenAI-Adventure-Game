Player sprite: Basic sprite sheet from itch.io

Llama3:8b
- Generate map descriptions
- Generate item icons 

->

SDXL
- Background image generation
- Generate multiple rooms
*** SWITCH TO OPENAI DALLE3 FOR FASTER, HIGHER QUALITY ***

->

David Kadish: Style Transfer for Object Detection in Art
- Object detection for stylized images (artwork)

-> 

(Hard code unity script that places objects in the scene)

->

Llama3:8b
- LLM
- For spatial placement of level exits
- For generating items that can be used for some simple puzzle (Item actions: COMBINE, INTERACT, TALK)

-------------------

User Journey:

User types text description
- (Llama3 to optimize user input for SDXL)

System generates series of items for puzzle, with interaction modes: TALK,TAKE,COMBINE(e.g. television + remote)
- Llama3

System generates scenes containing those items
- Input: Llama3 object names -> Output: SDXL item icons
- Input: Llama3 scene descriptions -> Output: SDXL scenes

System generates 




Nancy drew is investigating the roman colosseum at night. There are fireworks in the sky

mystical fountain in a dark cave with ambient light with foliage



TODO: move images into a ./res folder
