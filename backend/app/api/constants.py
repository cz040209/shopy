SYSTEM_INSTRUCTION = """You are Shopy Assistant, a concise and helpful shopping assistant for Shopy.
Help customers discover products, compare items, understand carts, orders, and ShopyPay.
Do not invent stock, order status, policies, prices, or account data that was not supplied.
Use clear, friendly language and ask one useful follow-up when needed."""

VISION_PROMPTS = {
    "shop_room": "Analyze this room for furniture, colours, style, empty spaces, and practical product recommendations. Give a concise shopping brief with 3-5 ideas.",
    "complete_look": "Use visible garments as the anchor for a coordinated outfit. Infer complementary wearable roles from the image framing and style, including useful off-frame roles when appropriate, without treating anatomy or grooming as shopping requests.",
    "shop_object": "Identify the main object in this photo and suggest similar or complementary products. Give a concise shopping brief with 3-5 ideas.",
}
