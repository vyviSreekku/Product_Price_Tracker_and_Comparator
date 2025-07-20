import os
from google import generativeai as genai

# Configure Gemini client
genai.configure(api_key=os.environ.get('GOOGLE_AI_API_KEY', 'your-google-ai-api-key'))  # Use environment variable for safety

def get_response(prompt, model="gemini-2.0-flash-latest", max_tokens=150, temp=0.3):
    model = genai.GenerativeModel(model)
    response = model.generate_content(
        prompt,
        generation_config=genai.types.GenerationConfig(
            temperature=temp,
            max_output_tokens=max_tokens,
        )
    )
    return response.text.strip()

def analyze_reviews(reviews_list):
    reviews_text = "\n".join(reviews_list)

    summary_prompt = (
        f"Summarize the following product reviews in a concise paragraph:\n{reviews_text}\nSummary:"
    )

    pros_prompt = (
        f"From the following product reviews, extract the top 5 **pros** as short phrases or aspects. If less than 5 pros, return all of them. "
        f"Format the output as a list with each pro starting with ✅ followed by two or three words (no full sentences). "
        f"Separate each item with a newline. Use ARSA format.\n\n"
        f"Product reviews:\n{reviews_text}\n\nPros:"
    )

    cons_prompt = (
        f"From the following product reviews, extract the top 5 **cons** as short phrases or aspects. If less than 5 cons, return all of them. "
        f"Format the output as a list with each con starting with ❌ followed by two or three words (no full sentences). "
        f"Separate each item with a newline. Use ARSA format.\n\n"
        f"Product reviews:\n{reviews_text}\n\nCons:"
    )

    summary = get_response(summary_prompt)
    pros = get_response(pros_prompt)
    cons = get_response(cons_prompt)

    return summary, pros, cons

# # Example usage
# if __name__ == "__main__":
#     reviews = [
#         "I love the product! The battery life is amazing and the sound quality is top-notch.",
#         "The product is good, but the build feels cheap and it gets hot quickly.",
#         "Excellent performance for the price, but I wish the display was brighter.",
#     ]

#     summary, pros, cons = analyze_reviews(reviews)
#     print("Summary:", summary)
#     print("\nPros:\n", pros)
#     print("\nCons:\n", cons)
