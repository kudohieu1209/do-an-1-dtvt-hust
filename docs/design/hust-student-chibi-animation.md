# HUST chibi welcome animation

Welcome mascot: approved red HUST crew-neck T-shirt concept. Logo and chatbot avatar use the book mark.

Runtime assets:
- `project/frontend/public/brand/hust-student-chibi.png`: approved character.
- `project/frontend/public/brand/hust-student-chibi-blink.png`: closed-eye frame, edited with the built-in imagegen tool.

`StudentWelcome.jsx` uses SVG masks to move the hand at the wrist and overlay the closed-eye regions, keeping the approved image intact. CSS plays two greeting waves on entry, one on interaction, and a brief blink every 6.4 seconds. Reduced-motion preferences disable these animations.

## Blink edit prompt

```text
Use case: precise-object-edit. Edit this approved transparent chibi HUST student into its closed-eye animation frame. Change ONLY the two open eyes into softly closed smiling eyelids with short dark curved lines, preserving natural skin shading over the former eyes. Do not change eyebrows, nose, mouth, smile, hair, head outline, pose, raised waving hand, shirt and its white HUST wordmark, backpack, trousers, shoes, proportions, colors, or linework. Exact registration is essential: keep the same 1254 by 1254 square canvas, same character scale, and every feature at exactly the same coordinates. The body and head must not move at all. Preserve genuine transparent background. No new objects, no scene, no captions, no crop. This image will be layered over the source image during a brief blink, so it must match the source everywhere except the eyes.
```

