# Fix Pagination Controls — Standard MUI-style Algorithm

## Problems
1. **Wrong page window**: Page 5 shows `1 … 5 … 4126` (only 3 middle slots because `midCount` is wrong). Page 3 shows `1 2 3 … 4126` (no page 4). Page 4 shows `1 3 4 … 4126` (missing page 2, page 1 jumps to 3).
2. **Layout shift**: Showing text width varies ("1-50" vs "151-200"), pushing the centered controls.

## Root Cause
The current algorithm tries to maintain a fixed number of slots (T=7) but the math for computing the middle window is broken. It computes `ws`/`we` based on `T` slots, then subtracts first/last/ellipsis from T to get `midCount`, but the clamping of `ms`/`me` to `[ws, we]` doesn't guarantee the current page is included.

## Solution: Standard `boundaryCount` + `siblingCount` Pattern

This is the well-known pattern used by MUI, Ant Design, etc.:
- `boundaryCount` = 1 (always show first and last page)
- `siblingCount` = 2 (show 2 pages on each side of current page)

This produces:
- Page 1 of 4126: `1 2 3 4 5 … 4126`
- Page 3 of 4126: `1 2 3 4 5 … 4126`
- Page 6 of 4126: `1 … 4 5 6 7 8 … 4126`
- Page 4126 of 4126: `1 … 4122 4123 4124 4125 4126`

The algorithm (from MUI's `usePagination` source):
```
1. Create a range of all page numbers: [1, 2, ..., totalPages]
2. Determine start pages: [1, ..., boundaryCount]
3. Determine end pages: [totalPages - boundaryCount + 1, ..., totalPages]
4. Determine sibling pages: [page - siblingCount, ..., page + siblingCount]
5. Merge, deduplicate, and sort
6. Add ellipsis between any gaps > 1
```

This naturally produces a variable number of slots (7-9 typically), which is fine — the width is stable because ellipsis and page buttons all use the same `minW`.

## Implementation Plan

### Step 1: Rewrite `pageSlots` using the standard algorithm
Replace the entire `pageSlots` useMemo with the MUI-style approach:
- `boundaryCount = 1`, `siblingCount = 2`
- Build start range, end range, sibling range
- Merge, sort, deduplicate
- Walk the sorted list, inserting ellipsis between gaps

### Step 2: Remove fixed-slot-count padding
No more `while (slots.length < T) push ellipsis`. The slot count varies naturally (7-9 slots) which is standard behavior. All slots use the same `btnMinW` so width is stable.

### Step 3: Fix showing text layout shift
Already partially fixed with `<Box minW="200px">` wrapper. Keep this approach — it's simple and effective.

### Step 4: Remove `MAX_VISIBLE_PAGES` constant
No longer needed since we use `boundaryCount` + `siblingCount`.

## Files Changed
- `frontend/src/pages/Review/index.tsx` — rewrite `pageSlots` algorithm

## Verification
- `cd frontend && node_modules/.bin/vite build --mode development` — should pass
- Manual verification of page window for pages 1, 2, 3, 4, 5, 6, 20, 4125, 4126
