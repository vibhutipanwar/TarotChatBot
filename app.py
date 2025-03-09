import os
import random
import time
import json
import google.generativeai as genai
import gradio as gr

import requests
from concurrent.futures import ThreadPoolExecutor
import threading

# API Key Configuration 
GEMINI_API_KEY = "Your_API_Key"

# Tarot deck information
MAJOR_ARCANA = [
    "The Fool", "The Magician", "The High Priestess", "The Empress",
    "The Emperor", "The Hierophant", "The Lovers", "The Chariot",
    "Strength", "The Hermit", "Wheel of Fortune", "Justice",
    "The Hanged Man", "Death", "Temperance", "The Devil",
    "The Tower", "The Star", "The Moon", "The Sun",
    "Judgement", "The World"
]

MINOR_ARCANA_SUITS = ["Cups", "Pentacles", "Swords", "Wands"]
MINOR_ARCANA_NUMBERS = [
    "Ace", "Two", "Three", "Four", "Five",
    "Six", "Seven", "Eight", "Nine", "Ten",
    "Page", "Knight", "Queen", "King"
]

# Reading types 
READING_TYPES = {
    "one_card": {
        "name": "One Card",
        "description": "A simple reading with one card for immediate guidance",
        "cards": 1
    },
    "three_card": {
        "name": "Three Card",
        "description": "Past, Present, Future",
        "cards": 3
    },
    "celtic_cross": {
        "name": "Celtic Cross",
        "description": "A 10-card comprehensive reading for complex situations",
        "cards": 10
    },
    "horseshoe": {
        "name": "Horseshoe",
        "description": "A 7-card spread for answering specific questions",
        "cards": 7
    },
    "relationship": {
        "name": "Relationship",
        "description": "A 5-card spread focusing on relationship dynamics",
        "cards": 5
    },
    "career_path": {
        "name": "Career Path",
        "description": "A 5-card spread about professional decisions",
        "cards": 5
    }
}


# Initialize the API
def initialize_api():
    if not GEMINI_API_KEY:
        print("Please add your Gemini API key as an environment variable.")
        return False

    # Initialize Gemini
    genai.configure(api_key=GEMINI_API_KEY)
    return True


# Generate full tarot deck
def generate_full_deck():
    deck = MAJOR_ARCANA.copy()
    for suit in MINOR_ARCANA_SUITS:
        for number in MINOR_ARCANA_NUMBERS:
            deck.append(f"{number} of {suit}")
    return deck


FULL_DECK = generate_full_deck()


# Image URLs for all 78 Tarot cards with fallback options
def generate_card_image_urls():
    card_images = {}

    # Used sacred-texts.com as primary source, with consistent URL formatting
    PRIMARY_URL_TEMPLATE = "https://www.sacred-texts.com/tarot/pkt/img/{}.jpg"
    FALLBACK_URL_TEMPLATE = "https://www.tarot.com/images/cards/rider-waite/{}.jpg"

    # Mapping for Major Arcana cards to URL-friendly formats for sacred-texts.com
    major_arcana_mapping = {
        "The Fool": "ar00", "The Magician": "ar01", "The High Priestess": "ar02",
        "The Empress": "ar03", "The Emperor": "ar04", "The Hierophant": "ar05",
        "The Lovers": "ar06", "The Chariot": "ar07", "Strength": "ar08",
        "The Hermit": "ar09", "Wheel of Fortune": "ar10", "Justice": "ar11",
        "The Hanged Man": "ar12", "Death": "ar13", "Temperance": "ar14",
        "The Devil": "ar15", "The Tower": "ar16", "The Star": "ar17",
        "The Moon": "ar18", "The Sun": "ar19", "Judgement": "ar20", "The World": "ar21"
    }

    # Mapping for Minor Arcana on sacred-texts.com.
    suit_codes = {"Cups": "cu", "Pentacles": "pe", "Swords": "sw", "Wands": "wa"}
    number_codes = {
        "Ace": "ac", "Two": "02", "Three": "03", "Four": "04", "Five": "05",
        "Six": "06", "Seven": "07", "Eight": "08", "Nine": "09", "Ten": "10",
        "Page": "pa", "Knight": "kn", "Queen": "qu", "King": "ki"
    }

    # Process Major Arcana cards
    for card in MAJOR_ARCANA:
        if card in major_arcana_mapping:
            code = major_arcana_mapping[card]
            fallback_code = code

            card_images[card] = {
                "primary": PRIMARY_URL_TEMPLATE.format(code),
                "fallback": FALLBACK_URL_TEMPLATE.format(fallback_code)
            }
        else:
            # Placeholder for any unmapped Major Arcana
            safe_name = card.lower().replace(" ", "-").replace("'", "")
            card_images[card] = {
                "primary": f"https://via.placeholder.com/150x250/673AB7/FFFFFF?text={safe_name}",
                "fallback": f"https://via.placeholder.com/150x250/673AB7/FFFFFF?text={safe_name}"
            }

    # Process Minor Arcana cards
    for suit in MINOR_ARCANA_SUITS:
        suit_code = suit_codes.get(suit, "")
        for number in MINOR_ARCANA_NUMBERS:
            card = f"{number} of {suit}"
            num_code = number_codes.get(number, "")

            # sacred-texts.com format: cu01, pe10, etc.
            code = f"{suit_code}{num_code}"

            # tarot.com format: cu-01, pe-10, etc.
            fallback_code = f"{suit_code}-{num_code}"

            card_images[card] = {
                "primary": PRIMARY_URL_TEMPLATE.format(code),
                "fallback": FALLBACK_URL_TEMPLATE.format(fallback_code)
            }

    return card_images


CARD_IMAGES = generate_card_image_urls()


# Card orientation (upright or reversed)
def get_card_with_orientation(card):
    orientation = random.choice(["Upright", "Reversed"])
    return {"card": card, "orientation": orientation}


# Draw cards for a reading
def draw_cards(num_cards):
    deck = FULL_DECK.copy()
    random.shuffle(deck)
    drawn_cards = []

    for _ in range(num_cards):
        card = deck.pop()
        drawn_cards.append(get_card_with_orientation(card))

    return drawn_cards


# Generate prompt for AI based on reading type
def generate_reading_prompt(reading_type, cards, question=""):
    prompt = f"You are a tarot reader creating a concise but insightful {READING_TYPES[reading_type]['name']} reading. "
    prompt += f"Question: '{question}'. "

    if reading_type == "one_card":
        prompt += f"Card: {cards[0]['card']} ({cards[0]['orientation']}). "

    elif reading_type == "three_card":
        prompt += "Cards: "
        prompt += f"Past: {cards[0]['card']} ({cards[0]['orientation']}), "
        prompt += f"Present: {cards[1]['card']} ({cards[1]['orientation']}), "
        prompt += f"Future: {cards[2]['card']} ({cards[2]['orientation']}). "

    elif reading_type == "celtic_cross":
        positions = [
            "Present", "Challenge", "Foundation", "Recent Past",
            "Potential", "Near Future", "Self", "Environment",
            "Hopes/Fears", "Outcome"
        ]
        prompt += "Cards: "
        for i, position in enumerate(positions):
            prompt += f"{position}: {cards[i]['card']} ({cards[i]['orientation']}), "

    elif reading_type == "horseshoe":
        positions = [
            "Past", "Present", "Hidden Influences", "Obstacles",
            "Environment", "Advice", "Outcome"
        ]
        prompt += "Cards: "
        for i, position in enumerate(positions):
            prompt += f"{position}: {cards[i]['card']} ({cards[i]['orientation']}), "

    elif reading_type == "relationship":
        positions = [
            "Self", "Partner", "Relationship Foundation",
            "Current Dynamics", "Potential/Outcome"
        ]
        prompt += "Cards: "
        for i, position in enumerate(positions):
            prompt += f"{position}: {cards[i]['card']} ({cards[i]['orientation']}), "

    elif reading_type == "career_path":
        positions = [
            "Current Situation", "Challenges", "Best Course of Action",
            "Factors to Consider", "Outcome"
        ]
        prompt += "Cards: "
        for i, position in enumerate(positions):
            prompt += f"{position}: {cards[i]['card']} ({cards[i]['orientation']}), "

    prompt += """
    Create a brief but impactful reading that:
    1. Gives key meanings of the cards in their positions
    2. Connects them to the question
    3. Provides clear guidance

    Keep your overall reading concise (under 400 words) to ensure fast generation.
    Use markdown formatting.
    """

    return prompt


# Get response from Gemini with timeout
def get_gemini_response(prompt, max_time=15):
    try:
        model = genai.GenerativeModel('gemini-1.5-pro')

        # Set a low temperature for faster response times
        generation_config = {
            "temperature": 0.7,
            "top_p": 0.8,
            "top_k": 40,
        }

        response = model.generate_content(
            prompt,
            generation_config=generation_config
        )
        return response.text
    except Exception as e:
        return f"Error with Gemini API: {str(e)}"


# Save reading history function
def save_reading_history(reading_type, question, cards, response):
    history = []
    try:
        if os.path.exists('tarot_history.json'):
            with open('tarot_history.json', 'r') as f:
                history = json.load(f)
    except:
        history = []

    history.append({
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "reading_type": reading_type,
        "question": question,
        "cards": cards,
        "response": response
    })

    try:
        with open('tarot_history.json', 'w') as f:
            json.dump(history, f, indent=2)
    except Exception as e:
        print(f"Could not save reading history: {str(e)}")


# Improved function to format cards as HTML for Gradio with better image loading
def format_cards_html(cards):
    # Determining how many cards we're displaying to adjust the layout
    card_count = len(cards)
    cards_per_row = min(4, card_count)  # Maximum 4 cards per row

    html = """<div style='
        display: flex; 
        flex-wrap: wrap; 
        padding: 20px;
        justify-content: center;
        background: linear-gradient(to right, rgba(103, 58, 183, 0.1), rgba(138, 43, 226, 0.2), rgba(103, 58, 183, 0.1));
        border-radius: 15px;
        box-shadow: 0 6px 16px rgba(0,0,0,0.1);
        margin-bottom: 20px;
    '>"""

    for i, card_info in enumerate(cards):
        card_name = card_info['card']
        orientation = card_info['orientation']

        # Get the image URLs from our dictionary
        image_urls = CARD_IMAGES.get(card_name, {"primary": "", "fallback": ""})

        # Set rotation for reversed cards
        rotation = "0deg" if orientation == "Upright" else "180deg"
        color = "#8A2BE2" if orientation == "Upright" else "#9932CC"
        glow = "0 0 15px rgba(138, 43, 226, 0.5)" if orientation == "Upright" else "0 0 15px rgba(153, 50, 204, 0.5)"

        # If this is a large spread like Celtic Cross, add more structure
        if card_count > 5 and i > 0 and i % cards_per_row == 0:
            html += """<div style="flex-basis: 100%; height: 20px;"></div>"""  # Row break

        # Create a more robust fallback mechanism
        safe_card_name = card_name.replace(' ', '-').replace("'", "")
        placeholder_url = f"https://via.placeholder.com/150x250/673AB7/FFFFFF?text={safe_card_name.replace(' ', '%20')}"

        html += f"""
        <div style="
            margin: 15px; 
            text-align: center;
            background-color: rgba(255, 255, 255, 0.1);
            padding: 15px;
            border-radius: 12px;
            backdrop-filter: blur(3px);
            transition: transform 0.3s;
            box-shadow: 0 4px 8px rgba(0,0,0,0.2);
            min-width: 180px;
        " onmouseover="this.style.transform='scale(1.05)'" onmouseout="this.style.transform='scale(1)'">
            <div style="
                transform: rotate({rotation}); 
                transition: transform 0.8s;
                margin-bottom: 12px;
                width: 150px;
                height: 250px;
                margin: 0 auto;
            ">
                <img src="{image_urls['primary']}" 
                     style="
                        width: 150px; 
                        height: 250px; 
                        border-radius: 10px; 
                        box-shadow: {glow};
                        border: 2px solid {color};
                        object-fit: cover;
                     " 
                     alt="{card_name}"
                     loading="eager" 
                     onerror="
                        if (!this.dataset.triedFallback) {{
                            this.dataset.triedFallback = 'true';
                            this.src = '{image_urls['fallback']}';
                        }} else if (!this.dataset.triedPlaceholder) {{
                            this.dataset.triedPlaceholder = 'true';
                            this.src = '{placeholder_url}';
                        }}
                     ">
            </div>
            <p style="
                margin-top: 12px; 
                margin-bottom: 4px; 
                font-weight: bold;
                font-family: 'Cinzel', serif;
                font-size: 16px;
                color: #673AB7;
            ">{card_name}</p>
            <p style="
                margin-top: 0; 
                color: {color};
                font-family: 'Philosopher', sans-serif;
                font-weight: 500;
            ">{orientation}</p>
        </div>
        """

    html += "</div>"

    # Add custom fonts
    html = """
    <link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Cinzel:wght@400;700&family=Philosopher:wght@400;700&display=swap">
    """ + html

    return html


# Helper function to get reading description
def get_reading_description(reading_type):
    return READING_TYPES[reading_type]['description']


# Main function for Gradio interface with optimization
def perform_reading(reading_type, question):
    if not question:
        question = "General guidance"

    # Set a timer to ensure we don't exceed 20 seconds
    start_total_time = time.time()

    # Draw cards
    num_cards = READING_TYPES[reading_type]["cards"]
    cards = draw_cards(num_cards)

    # Format cards as HTML
    cards_html = format_cards_html(cards)

    # Generate reading prompt
    prompt = generate_reading_prompt(reading_type, cards, question)

    # Get AI response with a timeout limit
    remaining_time = max(5, 20 - (time.time() - start_total_time))
    gemini_response = get_gemini_response(prompt, max_time=remaining_time)

    # If response is too long, trim it
    if len(gemini_response) > 1500:
        gemini_response = gemini_response[:1450] + "...\n\n*"

    total_time = time.time() - start_total_time

    # Format the response
    reading_header = f"# Your {READING_TYPES[reading_type]['name']} Reading\n\n"
    question_text = f"*Question: {question}*\n\n"
    time_info = f"\n\n*Generated in {total_time:.2f} seconds*"

    # Save reading history in the background to not delay response
    def save_history_background():
        save_reading_history(reading_type, question, cards, gemini_response)

    # Start a background thread to save history
    history_thread = threading.Thread(target=save_history_background)
    history_thread.daemon = True
    history_thread.start()

    return cards_html, reading_header + question_text + gemini_response + time_info


# Create and launch the Gradio interface
def create_gradio_interface():
    # Initialize API
    if not initialize_api():
        print("Failed to initialize Gemini API. Please check your API key.")
        return

    # Create reading type choices
    reading_choices = [(READING_TYPES[key]["name"], key) for key in READING_TYPES]

    # Define theme
    custom_theme = gr.themes.Soft(
        primary_hue="purple",
        secondary_hue="indigo",
        neutral_hue="slate",
        text_size=gr.themes.sizes.text_md
    )

    # Create the interface
    with gr.Blocks(theme=custom_theme, title="The Destiny Decoder - Tarot Reader") as app:
        gr.Markdown("# 🔮 The Destiny Decoder 🔮")
        gr.Markdown("### Your AI-powered guide to tarot insights")

        with gr.Row():
            with gr.Column(scale=1):
                reading_type = gr.Dropdown(
                    choices=reading_choices,
                    value=reading_choices[0][1],
                    label="Select Reading Type"
                )
                description = gr.Markdown(
                    get_reading_description(reading_choices[0][1])
                )
                reading_type.change(
                    lambda x: get_reading_description(x),
                    inputs=reading_type,
                    outputs=description
                )

                question = gr.Textbox(
                    placeholder="What guidance do you seek?",
                    label="Enter Your Question"
                )

                read_button = gr.Button("Draw Cards & Read", variant="primary")

            with gr.Column(scale=2):
                cards_output = gr.HTML(label="Your Cards")
                reading_output = gr.Markdown(label="Your Reading")

        # Add CSS for preloading
        gr.HTML("""
        <style>
        /* Style to ensure cards display nicely */
        img {
            max-width: 100%;
            height: auto;
            transition: opacity 0.3s;
        }
        </style>
        """)

        # Connect the button to the perform_reading function
        read_button.click(
            perform_reading,
            inputs=[reading_type, question],
            outputs=[cards_output, reading_output]
        )

        gr.Markdown("""
        ### About
        This app uses the Rider-Waite tarot card deck images and Google's Gemini AI to provide tarot readings.
        """)

        return app


# Launch the app
if __name__ == "__main__":
    app = create_gradio_interface()
    app.launch(share=True, server_port=8765)
