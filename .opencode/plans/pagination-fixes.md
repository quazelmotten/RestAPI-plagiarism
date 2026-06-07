# Fix Pagination UI Issues

## Problems
1. **Pagination bar not centered** — showing text and controls use `space-between`, pushing them to edges
2. **Inconsistent button widths** — page 4126 is wider than page 7, causing layout shift
3. **Asymmetric page window** — page 7 shows 1...4-10...4126 but page 1 shows 1-7...4126 (window not centered on active page)

## Fix 1: Center the bottom bar
- File: `frontend/src/pages/Review/index.tsx`, line ~683
- Change `<Flex justify="space-between" ...>` to `<Flex justify="center" gap={3}>`
- Remove the `total` prop from `<PaginationControls>` call (it's now passed separately; total is used only in the showing text here)
- Wrap `<PaginationControls>` directly inside the same `<Flex>` (no nested `<HStack>` wrapper needed since it already renders `<HStack>`)
- Add `whiteSpace="nowrap"` to showing text

## Fix 2: Fixed-width page buttons
- File: `frontend/src/pages/Review/index.tsx`, inside `PaginationControls`
- Calculate button width based on `totalPages` digit count:
  - `const buttonWidth = Math.max(32, String(totalPages).length * 8 + 16)` — or simply use `w` prop instead of `minW`
  - Simpler: compute `maxDigits = String(totalPages).length` and set `minW={`${maxDigits * 8 + 16}px`}` or just use a lookup
- Better approach: use `minW={`${Math.max(2.5, String(totalPages).length * 0.6 + 1.5)}rem`}` — scales reasonably
- Actually simplest: Chakra `size="sm"` buttons with fixed width — use `minW="38px"` for up to 4 digits, or compute dynamically:
  ```
  const btnMinW = useMemo(() => {
    const digits = String(totalPages).length;
    if (digits <= 2) return '32px';
    if (digits <= 3) return '40px';
    return `${32 + (digits - 2) * 8}px`;
  }, [totalPages]);
  ```
- Apply `minW={btnMinW}` to all page buttons AND spacer boxes AND ellipsis text AND goto button
- This ensures ALL slots have identical width regardless of digit count

## Fix 3: Symmetric sliding window
- File: `frontend/src/pages/Review/index.tsx`, `pageSlots` useMemo (line ~102)
- Change `MAX_VISIBLE_PAGES` from 7 to 5 (show 5 page numbers between prev/next/ellipsis)
- New algorithm:
  ```
  const VISIBLE = 5; // number of page number buttons shown
  
  if (totalPages <= VISIBLE + 2) {
    // Show all pages: 1 2 3 4 5 (no ellipsis needed)
    for (let i = 0; i < totalPages; i++) slots.push({ type: 'page', page: i });
    return slots;
  }
  
  // Always show first and last page, with a sliding window of VISIBLE pages around current
  // Window: [windowStart, windowStart + VISIBLE - 1], centered on `page`
  
  const half = Math.floor(VISIBLE / 2);
  let windowStart = page - half;
  let windowEnd = windowStart + VISIBLE - 1;
  
  // Clamp so we never go past the end
  if (windowEnd >= totalPages - 1) {
    windowEnd = totalPages - 2; // keep last page separate
    windowStart = windowEnd - VISIBLE + 1;
  }
  if (windowStart <= 0) {
    windowStart = 1; // keep first page separate
    windowEnd = windowStart + VISIBLE - 1;
  }
  
  // Always show page 1
  slots.push({ type: 'page', page: 0 });
  if (windowStart > 1) slots.push({ type: 'ellipsis' });
  
  // Window pages
  for (let i = windowStart; i <= windowEnd; i++) {
    slots.push({ type: 'page', page: i });
  }
  
  if (windowEnd < totalPages - 2) slots.push({ type: 'ellipsis' });
  slots.push({ type: 'page', page: totalPages - 1 });
  ```
- Remove the fixed 7-slot / spacer approach entirely — the window is now always symmetric
- No more spacers needed since first/last are always shown

## Files Changed
- `frontend/src/pages/Review/index.tsx` — all changes in this file

## Verification
- `cd frontend && node_modules/.bin/vite build --mode development` — should pass with no errors
