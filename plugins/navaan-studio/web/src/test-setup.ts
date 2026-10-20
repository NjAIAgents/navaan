import "@testing-library/jest-dom/vitest";

// jsdom has no layout; the rich editor (ProseMirror) asks for rectangles when it moves the cursor, so it is told there are none.
const noRects = () => ({ length: 0, item: () => null, [Symbol.iterator]: function* () { /* none */ } }) as unknown as DOMRectList;
if (typeof Range !== "undefined") { Range.prototype.getClientRects ??= noRects; Range.prototype.getBoundingClientRect ??= () => new DOMRect(); }
if (typeof Element !== "undefined") Element.prototype.getClientRects ??= noRects;
if (typeof document !== "undefined") document.elementFromPoint ??= () => null;
