import type { Theme, ThemeLogger } from 'ag-stack';
import type { CoreParams } from './core/core-css';
/** @internal AG_GRID_INTERNAL - Not for public use. Can change / be removed at any time. */
export declare const gridThemeLogger: ThemeLogger;
/**
 * Create a custom theme containing core grid styles but no parts.
 */
export declare const createTheme: () => Theme<CoreParams>;
