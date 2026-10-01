"use client";

/**
 * Compact pocket map: one small square per binder slot (216 / 360), filled squares in
 * gold. Readable at a glance without rendering hundreds of cards.
 */
export function SlotMap({ capacity, used, graded = 0 }: { capacity: number; used: number; graded?: number }) {
  const filled = Math.min(used, capacity);
  const gradedFilled = Math.min(graded, filled);
  return (
    <div>
      <div
        className="grid w-fit max-w-full gap-[3px]"
        style={{ gridTemplateColumns: `repeat(${capacity >= 300 ? 30 : 24}, minmax(0, 12px))` }}
        role="img"
        aria-label={`${filled} of ${capacity} pockets filled`}
      >
        {Array.from({ length: capacity }, (_, i) => (
          <span
            key={i}
            className={`aspect-square rounded-[2px] ${
              i < gradedFilled ? "bg-gold ring-1 ring-inset ring-amber-200/60" : i < filled ? "bg-gold/80" : "bg-surface-3"
            }`}
          />
        ))}
      </div>
      <div className="mt-2 flex flex-wrap items-center gap-x-4 gap-y-1 text-[11px] text-ink-3">
        <span className="flex items-center gap-1.5">
          <span className="h-2 w-2 rounded-[2px] bg-gold/80" /> filled
        </span>
        {gradedFilled > 0 && (
          <span className="flex items-center gap-1.5">
            <span className="h-2 w-2 rounded-[2px] bg-gold ring-1 ring-amber-200/60" /> graded
          </span>
        )}
        <span className="flex items-center gap-1.5">
          <span className="h-2 w-2 rounded-[2px] bg-surface-3" /> empty
        </span>
        {used > capacity && <span className="text-amber-300">{used - capacity} over capacity</span>}
      </div>
    </div>
  );
}
