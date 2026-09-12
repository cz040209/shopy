# Shopy complete AI demo video script

## Purpose

Show Shopy as an AI shopping system, not only an e-commerce storefront. The video demonstrates text, voice, and vision inputs; individual and bundle recommendations; alternatives; cart and checkout; and payment confirmation.

Target final length: 2 minutes 55 seconds to 3 minutes

Format: 16:9, 1920 x 1080, browser window only, English narration and English burned-in subtitles.

## Before recording

1. Start the frontend, backend, Redis, database, and worker services.
2. Sign in with a demo account with enough ShopyPay balance for the final order. If the wallet is not funded, top it up before recording the checkout section.
3. Confirm the catalog returns products for laptop, phone, house/furniture, mouse accessories, apparel, and car-care requests.
4. Keep these files in Downloads:
   - `emptyroom.jpg`
   - `mouse.jpg`
   - `human.jpg`
5. Use a fresh browser tab or restart the demo session between separate missions. Shopy retains short-term mission context intentionally, so this avoids one scenario influencing the next.
6. Turn on browser microphone permission before the voice scene. Do not show the permission prompt in the final take.
7. Clear the cart before the first scene. After the bundle alternative scene, add the selected bundle to the cart for checkout.

## Three-minute editing approach

This is a fast, feature-complete showcase. Record each interaction normally, but edit out waiting time and use 0.25 to 0.4 second crossfades between scenes. Keep these moments in the final video:

- the prompt or uploaded image;
- a very short processing-state glimpse;
- the recommendation or analysis result;
- the subtitle explaining the AI contribution.

This keeps every AI feature visible while fitting the final cut into three minutes. A raw recording will still take longer because model responses and uploads need time to finish.

## Recording rules

- Keep each final reveal on screen for 1 to 2 seconds; remove longer waits during editing.
- Move the cursor deliberately and keep it still while narration explains a result.
- Do not expose editor windows, terminals, API keys, development tools, or personal information.
- Use the on-screen subtitle text below verbatim or near-verbatim. Keep each subtitle to one or two short lines.

## Scene 1 - Opening: Shopy's AI commerce experience

Time: 0:00 to 0:10

Browser action:

1. Open the Shopy home page.
2. Slowly move the cursor over the mission input, microphone, and image button without clicking.

Narration:

"Shopy is an AI-powered commerce experience that understands shopping goals through text, voice, and images. It turns each request into a structured mission, searches verified catalog data, and produces recommendations that can be checked out directly."

Subtitles:

```text
Shopy turns text, voice, and images into shopping missions.
```

```text
AI understands the goal. Verified catalog data supports every recommendation.
```

## Scene 2 - Text input: single-product request without a budget

Time: 0:10 to 0:30

Browser action:

1. Click the main mission input.
2. Enter: `I want to buy a laptop.`
3. Click **Build my mission** or the visible mission-submit button.
4. Keep 1 second of the execution workspace, then cut to the recommendation cards and verified-output heading.

Narration:

"A simple text request becomes a structured shopping mission. Shopy identifies intent, searches the catalog, and returns a grounded laptop recommendation."

Subtitles:

```text
Text input: “I want to buy a laptop.”
```

```text
AI extracts the product intent and creates a shopping mission.
```

## Scene 3 - Text input: single-product request with a budget

Time: 0:30 to 0:45

Browser action:

1. Return to the home page or open a fresh mission tab.
2. Enter: `I want to buy a phone under RM 2,000 with a strong camera and all-day battery.`
3. Submit the mission.
4. Cut from the submitted prompt to the price range and product cards.

Narration:

"With a budget and priorities, the AI converts natural language into constraints and checks the selected phone against real catalog evidence."

Subtitles:

```text
Text input: phone under RM 2,000, with camera and battery priorities.
```

```text
AI converts natural language into budget, preference, and product constraints.
```

```text
Recommendations are checked against catalog facts and the available budget.
```

## Scene 4 - Text input: bundle request, then budgeted bundle request

Time: 0:45 to 1:15

Browser action:

1. Return home or open a fresh mission tab.
2. Enter: `I want to set up my new house.`
3. Keep a one-second glimpse of the planning state, then cut.
4. Start a fresh mission.
5. Enter: `I want to set up my new house with a budget of RM 8,000. I need a living-room and bedroom starter setup that feels warm, practical, and family-friendly.`
6. Submit and cut to the bundle cards.
7. Use a slow five-second scroll across the role labels, individual prices, and total.

Narration:

"For a larger goal, Shopy plans a bundle. It identifies required roles, finds compatible products, and checks the total against the budget."

Subtitles:

```text
Bundle request: setting up a new house.
```

```text
AI plans the shopping roles needed for the outcome, not just a single product.
```

```text
Each bundle is checked for role coverage, compatibility, prices, and total budget.
```

## Scene 5 - Alternative bundle options

Time: 1:15 to 1:28

Browser action:

1. On the house bundle result, scroll to **Alternative Bundles**.
2. Hold both alternatives in view for two seconds.
3. Click **Explore** on **Best value edit**.
4. Cut to the revised bundle and new total, then add the preferred item(s) to the cart.

Narration:

"Alternative bundles preserve the outcome while changing a clear trade-off, such as better value or a more premium finish."

Subtitles:

```text
Alternative bundles preserve the goal while changing a clear trade-off.
```

```text
Shopy recomposes the bundle using the active mission and verified catalog options.
```

## Scene 6 - Vision input: shop a room

Time: 1:28 to 1:45

Browser action:

1. Return to the home page.
2. Click the image/camera button.
3. Choose **Shop a room**.
4. Choose **Gallery** and upload `~/Downloads/emptyroom.jpg`.
5. Click **Use photo**, retain a one-second AI-analysis glimpse, then cut to room opportunities and recommendations.

Narration:

"For a room photo, vision AI detects space, style, colours, and shopping opportunities before guiding catalog search."

Subtitles:

```text
Vision input: Shop a room.
```

```text
AI analyzes the room's visible space, style, colours, and shopping opportunities.
```

```text
Visual context guides catalog search without replacing verified product data.
```

## Scene 7 - Vision input: shop a similar object

Time: 1:45 to 1:57

Browser action:

1. Return to the home page and open the image/camera button again.
2. Choose **Shop an object**.
3. Choose **Gallery** and upload `~/Downloads/mouse.jpg`.
4. Click **Use photo**, then cut to matching or complementary recommendations.

Narration:

"For an object photo, vision AI identifies the item and finds similar or complementary products."

Subtitles:

```text
Vision input: Shop an object.
```

```text
AI recognizes the visible object and searches for similar or complementary products.
```

## Scene 8 - Vision input: complete a look

Time: 1:57 to 2:09

Browser action:

1. Return to the home page and open the image/camera button again.
2. Choose **Complete a look**.
3. Choose **Gallery** and upload `~/Downloads/human.jpg`.
4. Click **Use photo**, then cut to styling recommendations.

Narration:

"For style shopping, vision AI uses outfit and colour context to recommend complementary wearable products."

Subtitles:

```text
Vision input: Complete a look.
```

```text
AI uses outfit and style context to recommend complementary wearable products.
```

## Scene 9 - Voice input

Time: 2:09 to 2:24

Browser action:

1. Return to the home page.
2. Click the microphone button and speak clearly:
   `Build me a car care kit under RM 400 for a weekly wash.`
3. Click the microphone again to stop recording.
4. Cut to the transcript appearing in the mission input.
5. Show it briefly, submit the mission, then cut to the recommendation.

Narration:

"Voice is transcribed for customer review, then enters the same AI mission workflow as text and vision."

Subtitles:

```text
Voice input: “Build me a car care kit under RM 400 for a weekly wash.”
```

```text
Speech is transcribed, reviewed, and converted into the same structured AI mission.
```

## Scene 10 - Cart, checkout, and payment confirmation

Time: 2:24 to 2:50

Browser action:

1. Return to the cart containing the selected house-bundle item(s).
2. Show the cart for two seconds, then click **Checkout**.
3. Hold the order summary, ShopyPay balance, and payment details for three seconds.
4. Click the final checkout/payment button.
5. Keep one second of **Processing your payment**.
6. Hold **Payment confirmed** for four seconds.

Narration:

"The AI shopping journey ends in commerce: selected catalog products move to cart, ShopyPay confirms payment, and the order receipt workflow begins."

Subtitles:

```text
Recommended products move directly into a standard commerce checkout.
```

```text
Payment confirmed. The order is created and the receipt workflow is triggered.
```

```text
Shopy records the confirmed order and prepares its invoice and receipt workflow.
```

## Closing card

Time: 2:50 to 3:00

Browser action:

1. Let Shopy return to the home page.
2. Hold the page still for two seconds.

Narration:

"From a message, voice note, or photo to a verified recommendation and checkout, Shopy brings AI intelligence into the complete shopping journey."

Subtitles:

```text
Shopy: AI-powered shopping from intent to checkout.
```

## Optional technical overlay captions

Use these short overlays only when you want a more technical competition version. Do not show all of them at once.

```text
Multimodal input -> structured shopping mission
```

```text
LangGraph specialist agents coordinate planning and selection
```

```text
Qwen vision analyzes visual context
```

```text
Catalog retrieval keeps recommendations grounded in real products
```

```text
Compatibility, totals, stock, and claims are checked before output
```

```text
Short-term memory supports relevant follow-up recommendations
```
