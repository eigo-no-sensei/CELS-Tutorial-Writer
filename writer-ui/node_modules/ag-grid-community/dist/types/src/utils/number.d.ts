import type { LocaleTextFunc } from 'ag-stack';
/** @internal AG_GRID_INTERNAL - Not for public use. Can change / be removed at any time. */
export declare function _isFiniteNumber(v: unknown): v is number;
/**
 * @internal AG_GRID_INTERNAL - Not for public use. Can change / be removed at any time.
 * Note: `Number('')` and `Number(' ')` are `0`, so callers must pre-filter blank strings if needed.
 */
export declare function _toFiniteNumber(v: unknown): number | null;
/** @internal AG_GRID_INTERNAL - Not for public use. Can change / be removed at any time. */
export declare function _clamp(value: number, min: number, max: number): number;
/**
 * the native method number.toLocaleString(undefined, {minimumFractionDigits: 0})
 * puts in decimal places in IE, so we use this method instead
 * from: http://blog.tompawlak.org/number-currency-formatting-javascript
 * @param {number} value
 * @returns {string}
 * @internal AG_GRID_INTERNAL - Not for public use. Can change / be removed at any time.
 */
export declare function _formatNumberCommas(value: number | null, getLocaleTextFunc: () => LocaleTextFunc): string;
