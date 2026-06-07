# Bulk Operations UX Review & Implementation Plan

> **For Hermes:** This is a planning/analysis document, not an implementation plan for subagent-driven-development. Implement tasks sequentially after review.

**Goal:** Fix bulk confirm/clear operations so they work reliably on the global Review page, provide clear user feedback during long-running operations, and ensure the UI correctly reflects state changes afterward.

**Core Problem:** After performing a bulk operation on the global Review page, pairs don't appear in the expected tab, and on refresh the list content shifts/disappears.

---

## Findings & Root Cause Analysis

### Problem 1: Pairs "Switch Places and Keep Disappearing" After Refresh

**Root cause: The global Review page's tab-to-status mapping is WRONG for the "Confirmed" and "Cleared" tabs.**

The Review page (`frontend/src/pages/Review/index.tsx:98-106`) maps tabs like this:
```
Tab 0 (To Review)  -> undefined (no status filter)
Tab 1 (All)        -> 'all'
Tab 2 (Confirmed)  -> 'plagiarism'  
Tab 3 (Cleared)    -> 'clear'
```

But the global `get_global_review_queue` backend endpoint (`src/results/service.py:978-989`) maps the `status` query parameter like this:
```
"plagiarism" or "confirmed" -> review_disposition == "plagiarism"
"bulk_confirmed"            -> review_disposition == "bulk_confirmed"
"clear" or "cleared"        -> review_disposition == "clear"
"unreviewed"                -> review_disposition IS NULL
```

So Tab 2 (Confirmed) correctly filters for `plagiarism` dispositions. But here's the critical issue:

**Bulk confirm sets `review_disposition = "bulk_confirmed"` (not `"plagiarism"`)**. So after a bulk confirm, pairs go to the `bulk_confirmed` disposition. But the Review page has NO tab for `bulk_confirmed`! The user clicks bulk confirm, then looks at the "Confirmed" tab, and sees nothing changed.

The assignment-specific `ReviewQueue.tsx` DOES have a Tab 3 for `bulk_confirmed`, but the global `Review/index.tsx` only has 4 tabs (indexes 0-3) and maps Tab 2 to `plagiarism` only.

### Problem 2: Stale Data / List Shifting After Refresh

**Root cause: The `useReviewQueue` hook has `staleTime: 10_000` (10 seconds).**

After a bulk operation, `refetch()` is called, but within the 10-second stale window React Query may return cached data. Additionally, the global review queue's total count changes after a bulk operation, but the frontend doesn't invalidate the cache aggressively enough.

The more subtle issue: when bulk confirm changes 1000 pairs from `NULL` to `bulk_confirmed`, the "To Review" tab's `total` count drops. But the `status` filter for Tab 2 sends `status=plagiarism` which does NOT include `bulk_confirmed`. So the user sees confirmed pairs only if they were individually confirmed (disposition=`plagiarism`), not bulk-confirmed.

### Problem 3: No User Feedback During/After Bulk Operations

The current flow:
1. User clicks Bulk Confirm, sets threshold, clicks "Confirm All"
2. Backend runs a single SQL UPDATE (fast for small datasets, but could be slow for millions of rows)
3. Frontend shows a toast "Bulk confirm complete" with no count of affected pairs
4. User has no idea if it worked, how many pairs were affected, or where to find them

Issues:
- The toast says "Bulk confirm complete" but doesn't say HOW MANY pairs were confirmed
- The "Confirmed" tab doesn't show bulk-confirmed pairs
- No visual indication of what just happened
- For very large operations, the user sees a spinner with no progress info

### Problem 4: Bulk Clear Threshold Default Is Confusing

The Review page's bulk clear dialog defaults `bulkClearClearThreshold` to `'0'`. Looking at the backend logic:
- `bulk_clear` with `threshold=0`: the `if threshold > 0` condition is FALSE, so it clears ALL unreviewed pairs (no similarity cap)
- `bulk_clear` with `threshold=0.5`: only clears unreviewed pairs with `ast_similarity <= 0.5`

The dialog says "Clear all pairs below threshold" but the default of 0 actually means "clear ALL pairs" (since the `<= 0` filter is skipped). This is confusing UX - the default should probably be something like 0.3 or the UI should clearly explain what threshold=0 means.

### Problem 5: Mismatch Between Assignment-Specific and Global Behavior

`ReviewQueue.tsx` (assignment-specific) has 5 tabs including "Bulk Confirmed". `Review/index.tsx` (global) has 4 tabs with no "Bulk Confirmed" tab. This means:

- On the assignment page: bulk confirm -> user can see results in "Bulk Confirmed" tab
- On the global page: bulk confirm -> results are invisible (no tab for them)

---

## Recommendations

### Recommendation 1: Add "Bulk Confirmed" Tab to Global Review Page
**Priority: HIGH** — This is why users can't see their bulk-confirmed pairs.

Add a `bulk_confirmed` tab (Tab 3) between "Confirmed" and "Cleared" in the global Review page:
```
Tab 0: To Review    -> unreviewed (no filter)
Tab 1: All          -> all (no filter)  
Tab 2: Confirmed    -> plagiarism
Tab 3: Bulk Confirmed -> bulk_confirmed
Tab 4: Cleared      -> clear
```

Files to modify:
- `frontend/src/pages/Review/index.tsx` — Add tab, update `getCurrentStatus()` mapping
- `frontend/src/pages/Review/index.tsx` — Update tab rendering to show 5 tabs

### Recommendation 2: Show Pair Count in Toast After Bulk Operations
**Priority: HIGH** — Users need confirmation that something happened.

Both `Review/index.tsx` and `ReviewQueue.tsx` already have access to `response.data.confirmed_pairs` from the `BulkConfirmResponse`. The toast should include this count:
```
"Bulk confirm complete: 847 pairs confirmed"
"Bulk clear complete: 1,203 pairs cleared"
```

### Recommendation 3: Improve Cache Invalidation After Bulk Operations
**Priority: MEDIUM** — Fixes the "disappearing pairs on refresh" issue.

After a bulk operation, the queries for ALL tabs are affected (unreviewed count goes down, confirmed/bulk_confirmed/cleared counts go up). The current code only calls `refetch()` which refetches the current tab's data. Instead:
1. Invalidate the entire `review-query` cache after any bulk operation
2. Or invalidate all queries that could be affected

### Recommendation 4: Add Loading State to Bulk Buttons
**Priority: MEDIUM** — Prevents double-clicks and gives feedback during long operations.

For large datasets (10M+ pairs), the UPDATE query could take seconds to minutes. Currently:
- The dialog stays open during the operation
- The button has no loading state
- The user can click again, sending duplicate requests

Fix:
- Add `isLoading` state to the bulk confirm/clear buttons
- Disable the button and show a spinner while the operation is in flight
- Close the dialog only after success
- For very large operations, consider showing a progress indicator

### Recommendation 5: Clarify Bulk Clear Threshold Behavior
**Priority: MEDIUM** — Prevents accidental clearing of all pairs.

The bulk clear dialog should:
1. Default to `0.3` instead of `0` (clear only low-similarity unreviewed pairs by default)
2. Add explanatory text: "Clears all unreviewed pairs with similarity ≤ threshold. Set to 0 to clear ALL unreviewed pairs."
3. Or better: split into two actions:
   - "Clear low-similarity pairs" (with configurable threshold, default 0.3)
   - "Clear ALL unreviewed" (destructive, requires confirmation)

### Recommendation 6: For Very Large Operations (10M+ pairs), Add Async Processing
**Priority: LOW** — Performance optimization for extreme cases.

The current bulk operations are synchronous SQL UPDATEs. For 10M+ rows this could:
- Take minutes to complete
- Hold a database transaction open
- Timeout the HTTP request

Options:
1. Keep synchronous but add a timeout-friendly approach (increase statement_timeout)
2. Add a backend task queue (Celery/async) that processes in batches
3. At minimum, add client-side polling to detect when the operation is truly done

For now, the single SQL UPDATE approach is fine for most real-world datasets (thousands to low millions of pairs). The main concern is UI feedback.

---

## Step-by-Step Implementation Plan

### Task 1: Add "Bulk Confirmed" Tab to Global Review Page

**Files:**
- Modify: `frontend/src/pages/Review/index.tsx:42-69` (ReviewTabs component)
- Modify: `frontend/src/pages/Review/index.tsx:98-106` (getCurrentStatus)

**Step 1: Update the global ReviewTabs to include 5 tabs**

In `frontend/src/pages/Review/index.tsx`, update the `ReviewTabs` component to accept `bulkConfirmedCount`:

```tsx
const ReviewTabs: React.FC<{
  activeTab: number;
  setActiveTab: (tab: number) => void;
  unreviewedCount: number;
  bulkConfirmedCount: number;
}> = ({ activeTab, setActiveTab, unreviewedCount, bulkConfirmedCount }) => {
  const { t } = useTranslation();
  const tabs = [
    { label: t('review:toReview'), color: 'red' },
    { label: t('review:all'), color: 'blue' },
    { label: t('review:confirmed'), color: 'orange' },
    { label: t('review:bulkConfirmed'), color: 'yellow' },
    { label: t('review:cleared'), color: 'green' },
  ];
  // ... render tabs
};
```

**Step 2: Update `getCurrentStatus` mapping**

```tsx
const getCurrentStatus = () => {
  switch (activeTab) {
    case 0: return undefined;        // To Review (unreviewed)
    case 1: return 'all';            // All
    case 2: return 'plagiarism';     // Confirmed
    case 3: return 'bulk_confirmed'; // Bulk Confirmed (NEW)
    case 4: return 'clear';          // Cleared
    default: return undefined;
  }
};
```

**Step 3: Pass `bulkConfirmedCount` to ReviewTabs**

Need to fetch global review status for the count. The Review page currently only uses `useReviewQueue` which returns paginated pairs. Need to add a `useQuery` for global review status.

Add to Review page:
```tsx
const { data: globalStatus } = useQuery({
  queryKey: ['global-review-status'],
  queryFn: async () => {
    const res = await api.get('/plagiarism/review-status');
    return res.data;
  },
});
```

Then pass counts:
```tsx
<ReviewTabs
  activeTab={activeTab}
  setActiveTab={setActiveTab}
  unreviewedCount={globalStatus?.unreviewed || 0}
  bulkConfirmedCount={globalStatus?.bulk_confirmed || 0}
/>
```

And update the tab switch to compute total for each tab:
```tsx
const totalForTab = activeTab === 0 ? (globalStatus?.unreviewed ?? 0)
  : activeTab === 1 ? (globalStatus?.total_pairs ?? 0)
  : activeTab === 2 ? (globalStatus?.confirmed ?? 0)
  : activeTab === 3 ? (globalStatus?.bulk_confirmed ?? 0)
  : (globalStatus?.cleared ?? 0);
```

**Step 4: Build and verify**

```bash
cd frontend && npm run build
```

### Task 2: Show Pair Count in Bulk Operation Toast Messages

**Files:**
- Modify: `frontend/src/pages/Review/index.tsx:219-220` (bulk confirm toast)
- Modify: `frontend/src/pages/Review/index.tsx:249-250` (bulk clear toast)
- Modify: `frontend/src/components/Review/ReviewQueue.tsx:217` (assignment bulk confirm toast)
- Modify: `frontend/src/components/Review/ReviewQueue.tsx:235` (assignment bulk clear toast)

**Step 1: Update Review page toasts**

In `handleBulkConfirm`, the response already has `confirmed_pairs`:
```tsx
// Before:
toast({ title: 'Bulk confirm complete', description: 'Bulk confirm operation completed', ... });

// After:  
const result = await api.post(endpoint, null, { params: { threshold } });
toast({
  title: 'Bulk confirm complete',
  description: `Confirmed ${result.data.confirmed_pairs} pairs above ${(threshold * 100).toFixed(0)}% similarity`,
  status: 'success',
  duration: 5000
});
```

**Step 2: Update ReviewQueue toasts similarly**

Both `handleBulkConfirm` and `handleBulkClear` in `ReviewQueue.tsx` already use `response.data.confirmed_pairs` but the assignment `Review/index.tsx` doesn't capture the response.

**Step 3: Build and verify**

### Task 3: Aggressive Cache Invalidation After Bulk Operations

**Files:**
- Modify: `frontend/src/pages/Review/index.tsx:204-264` (handleBulkConfirm/handleBulkClear)
- Modify: `frontend/src/components/Review/ReviewQueue.tsx:204-246` (same)

**Step 1: Use QueryClient to invalidate all review-related queries**

In `Review/index.tsx`, import `useQueryClient` from `@tanstack/react-query` and after successful bulk operations:
```tsx
const queryClient = useQueryClient();

// After successful bulk confirm/clear:
queryClient.invalidateQueries({ queryKey: ['review-queue'] });
queryClient.invalidateQueries({ queryKey: ['global-review-status'] });
queryClient.invalidateQueries({ queryKey: ['review-status'] });
```

Do the same in `ReviewQueue.tsx`:
```tsx
queryClient.invalidateQueries({ queryKey: ['reviewQueue'] });
queryClient.invalidateQueries({ queryKey: ['reviewStatus'] });
queryClient.invalidateQueries({ queryKey: ['pairsByStatus'] });
```

### Task 4: Add Loading State to Bulk Action Buttons

**Files:**
- Modify: `frontend/src/pages/Review/index.tsx:498-562` (AlertDialog components)
- Modify: `frontend/src/components/Review/ReviewQueue.tsx:472-536` (same)

**Step 1: Add loading state to Review page**

```tsx
const [isBulkConfirming, setIsBulkConfirming] = useState(false);
const [isBulkClearing, setIsBulkClearing] = useState(false);

// In handleBulkConfirm:
setIsBulkConfirming(true);
try {
  // ... api call ...
} finally {
  setIsBulkConfirming(false);
}

// In dialog:
<Button 
  colorScheme="orange" 
  onClick={handleBulkConfirm} 
  isLoading={isBulkConfirming} 
  loadingText="Confirming..."
  ml={3}
>
  {t('review:confirmAll')}
</Button>
```

Similarly for bulk clear with `isBulkClearing` / `loadingText="Clearing..."`.

**Step 2: Build and verify**

### Task 5: Clarify Bulk Clear Threshold UX

**Files:**
- Modify: `frontend/src/pages/Review/index.tsx:87` (default threshold)
- Modify: `frontend/src/pages/Review/index.tsx:528-562` (bulk clear dialog)
- Modify: `frontend/src/components/Review/ReviewQueue.tsx:64` (default threshold)
- Modify: `frontend/src/components/Review/ReviewQueue.tsx:501-536` (bulk clear dialog)

**Step 1: Change default threshold from '0' to '0.3'**

```tsx
const [bulkClearThreshold, setBulkClearThreshold] = useState('0.3');
```

**Step 2: Add explanatory text in the dialog**

Add to the bulk clear AlertDialogBody:
```tsx
<Text fontSize="xs" color="gray.500">
  Clears all unreviewed pairs with similarity ≤ threshold. 
  Lower threshold = fewer pairs cleared. Default: 30%.
</Text>
```

---

## Files Summary

| File | Change |
|------|--------|
| `frontend/src/pages/Review/index.tsx` | Add `bulk_confirmed` tab, global status query, cache invalidation, loading states, toast counts, threshold default |
| `frontend/src/components/Review/ReviewQueue.tsx` | Cache invalidation, loading states, toast counts, threshold default |
| `frontend/src/components/Review/ReviewTabs.tsx` | May need update if used globally (currently `Review/index.tsx` has its own inline `ReviewTabs`) |

---

## Risks & Tradeoffs

1. **Adding a 5th tab may be cramped on mobile** — consider responsive layout or collapsing into a dropdown
2. **Global status query adds an extra HTTP request** — minimal overhead, but consider combining with the review queue response in the future
3. **Synchronous bulk UPDATE for 10M+ rows** — could timeout; consider async task queue for very large datasets (out of scope for this plan)
4. **Cache invalidation is aggressive** — invalidating all queries could cause a brief flicker as all tabs refetch; this is acceptable for correctness

---

## Open Questions

1. Should bulk-confirmed pairs ALSO appear in the "Confirmed" tab (merged view), or should they stay separate?
   - **Recommendation:** Keep separate tabs but consider a combined "All Confirmed" view in the future
2. Should there be an "Undo Bulk" operation?
   - **Recommendation:** Out of scope for now; individual undo via `undo_review` endpoint already exists
3. Should the bulk clear threshold default be configurable per-user?
   - **Recommendation:** No, keep it simple; 0.3 is a sensible default
