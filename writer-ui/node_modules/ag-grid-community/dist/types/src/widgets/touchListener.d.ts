import type { AgEvent, IEventEmitter, IEventListener } from 'ag-stack';
export interface TapEvent extends AgEvent<'tap'> {
    touchStart: Touch;
}
export interface DoubleTapEvent extends AgEvent<'doubleTap'> {
    touchStart: Touch;
}
export interface LongTapEvent extends AgEvent<'longTap'> {
    touchStart: Touch;
    touchEvent: TouchEvent;
}
export type TouchListenerEvent = 'tap' | 'doubleTap' | 'longTap';
export declare class TouchListener implements IEventEmitter<TouchListenerEvent> {
    private eElement;
    private readonly preventClick;
    private startListener;
    private readonly handlers;
    private eventSvc;
    private touchStart;
    private lastTapTime;
    private longPressTimer;
    private moved;
    private longTapFired;
    private longTapListeners;
    constructor(eElement: Element, preventClick?: boolean);
    addEventListener<T extends TouchListenerEvent>(eventType: T, listener: IEventListener<T>): void;
    removeEventListener<T extends TouchListenerEvent>(eventType: T, listener: IEventListener<T>): void;
    private onTouchStart;
    private onTouchMove;
    private onTouchEnd;
    private onTouchCancel;
    private checkDoubleTap;
    private cancel;
    private clearLongPress;
    destroy(): void;
}
