# Fix Pagination — Fixed 5-Page Sliding Window

## Behavior Specification
Always exactly **7 page/ellipsis slots** between prev and next buttons:
- A 5-page window that slides with the current page
- At boundaries, the window clamps: page 1 → [1,2,3,4,5], page 4126 → [4122..4126]
- Ellipsis appears when there's a gap between the window and the boundary page

## Concrete Examples (4126 total pages)
- Page 1:   `1 2 3 4 5 … 4126`       (window [1..5], no lead ellipsis, window touches start)
- Page 3:   `1 2 3 4 5 … 4126`       (window [1..5], clamped at start)
- Page 4:   `1 2 3 4 5 … 4126`       (window [2..6] but 2-5 overlap start → expand to show 1-5)
- Page 5:   `1 2 3 4 5 … 4126`       (window [3..7] but 3-5 overlap start → expand to show 1-5)
- Page 6:   `1 … 4 5 6 7 8 … 4126`   (window [4..8], lead + trail ellipsis)
- Page 10:  `1 … 8 9 10 11 12 … 4126` (window [8..12])
- Page 20:  `1 … 18 19 20 21 22 … 4126`
- Page 4125: `1 … 4121 4122 4123 4124 4125 4126` (window [4121..4125])
- Page 4126: `1 … 4122 4123 4124 4125 4126` (window [4122..4126], clamped at end, no trail ellipsis)

## Algorithm
```
WINDOW = 5
HALF = 2  // floor(5/2)

ws = page - HALF
we = page + HALF

// Clamp-but-expand: if window overflows one side, shift it
if (ws < 0) { ws = 0; we = WINDOW - 1 }
if (we >= totalPages) { we = totalPages - 1; ws = totalPages - WINDOW }

// Build 7 slots: [first?] [ellipsis?] [window pages] [ellipsis?] [last?]
slots = []

// Leading: if window doesn't start at page 0, show page 0 + ellipsis
if (ws > 0) {
  slots.push(page: 0)
  if (ws > 1) slots.push(ellipsis)
}

// Window pages
for i in [ws..we]: slots.push(page: i)

// Trailing: if window doesn't end at last page, show ellipsis + last page
if (we < totalPages - 1) {
  if (we < totalPages - 2) slots.push(ellipsis)
  slots.push(page: totalPages - 1)
}
```

This always produces exactly 7 slots.

## Changes
- `frontend/src/pages/Review/index.tsx`:
  - Remove `BOUNDARY_COUNT`/`SIBLING_COUNT` constants
  - Replace `pageSlots` useMemo with the fixed 5-page sliding window algorithm above
  - Set `btnMinW` to always reserve width for `totalPages` digits on ALL items (prev, next, ellipsis, page buttons, goto)
  - Always render goto button (even when closed) as a ghost button with `…` text, replacing it with input when open — keeps width constant

## Verification
- `cd frontend && node_modules/.bin/vite build --mode development`
