import { BeanStub } from '../../context/beanStub';
import type { AgColumn } from '../../entities/agColumn';
import type { CellFocusedEvent } from '../../events';
import type { RefreshRowsParams } from '../../interfaces/iCellsParams';
import type { ColumnPinnedType } from '../../interfaces/iColumn';
import type { UserCompDetails } from '../../interfaces/iUserCompDetails';
import type { INotesFeature } from '../../interfaces/notes';
import type { CellCtrl } from '../cell/cellCtrl';
import type { ICellRenderer } from '../cellRenderers/iCellRenderer';
import type { FullWidthTarget, IRowModeFeature } from './iRowModeFeature';
import type { RowCtrl } from './rowCtrl';
export declare class FullWidthRowFeature extends BeanStub implements IRowModeFeature {
    private readonly rowCtrl;
    private tooltipFeature;
    private notesFeature;
    private focusEventWhileNotReady;
    constructor(rowCtrl: RowCtrl);
    initialiseComp(): void;
    refreshRow(_params: RefreshRowsParams): void;
    private refreshFullWidthComp;
    shouldCreateCellSections(): boolean;
    getModeCellRenderers(): (ICellRenderer | null | undefined)[];
    getAllCellCtrls(): CellCtrl[];
    recreateCell(_cellCtrl: CellCtrl): void;
    destroyCells(): void;
    onDisplayedColumnsChanged(): void;
    onVirtualColumnsChanged(): void;
    onColumnMoved(): void;
    onSpannedCellsUpdated(_pinned: ColumnPinnedType): void;
    createFullWidthCompDetails(eRow: HTMLElement, pinned: ColumnPinnedType): UserCompDetails;
    setupDetailRowAutoHeight(eDetailGui: HTMLElement): void;
    private setupFullWidthRowTooltip;
    /**
     * Wires up the tooltip for a full-width group row (`groupDisplayType: 'groupRows'`), inheriting the
     * tooltip configuration from the owning group column rather than from an individual cell.
     *
     * The tooltip source colDef is the row-group column's colDef for regular grouping, or the
     * `autoGroupColumnDef` for tree data (where there is no `rowGroupColumn`). If that colDef declares no
     * `tooltipValueGetter`, `tooltipField`, or `tooltipComponent`, no tooltip is set up.
     *
     * Resolution order, mirroring the standard cell tooltip path, with values lazily computed on hover:
     * - `tooltipValueGetter` — invoked with the group's display value/formatted value and full row context.
     * - `tooltipField` — read directly from `node.data`, honouring `suppressFieldDotNotation` for dotted fields.
     * - otherwise — falls back to the group display value, also passed to any inherited `tooltipComponent`.
     */
    private setupGroupRowsTooltip;
    private addFullWidthRowDragging;
    setupFocus(): void;
    private restoreFullWidthFocus;
    onRowFocused(event?: CellFocusedEvent): void;
    onKeyboardNavigate(keyboardEvent: KeyboardEvent): void;
    onTabKeyDown(keyboardEvent: KeyboardEvent): void;
    getRowContentElement(): HTMLElement | null;
    getNavigationColumn(): AgColumn;
    onRowMouseDown(mouseEvent: MouseEvent): void;
    isSuppressMouseEvent(mouseEvent: MouseEvent): boolean;
    getTargets(): FullWidthTarget[];
    getTarget(element?: EventTarget | null): FullWidthTarget | undefined;
    private getDefaultTarget;
    findInfoForEvent(event?: Event): {
        column: AgColumn;
        pinned: ColumnPinnedType;
    } | undefined;
    private addFullWidthTarget;
    private getFirstColumnForFullWidthSection;
    private getFirstDisplayedColumnForFullWidth;
    getNotesFeature(): INotesFeature | undefined;
    addInitialRowClasses(classes: string[]): void;
    destroy(): void;
}
