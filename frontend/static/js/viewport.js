/**
 * Viewport class for handling interactive panning and zooming (2D transformations)
 * on a canvas or container element. Works with mouse events.
 */
export class Viewport {
    constructor(container, viewportElement, options = {}) {
        this.container = container;             // The viewport wrapper/container (overflow hidden, handles mouse inputs)
        this.viewport = viewportElement;        // The transformed canvas container (applies transform: translate() scale())
        
        this.scale = options.initialScale !== undefined ? options.initialScale : 1.0;
        this.panX = options.initialPanX !== undefined ? options.initialPanX : 0;
        this.panY = options.initialPanY !== undefined ? options.initialPanY : 0;
        
        this.minScale = options.minScale || 0.15;
        this.maxScale = options.maxScale || 3.0;
        
        this.isPanning = false;
        this.startX = 0;
        this.startY = 0;
        
        this.onTransformChange = options.onTransformChange || null;
        
        this.init();
    }
    
    init() {
        // The viewport element is the CSS transform target (pan + zoom).
        // Its size is intentionally NOT set here — the virtual canvas (4000×4000px)
        // sets its own size. Only transform-origin matters for correct zoom-around-cursor.
        this.viewport.style.transformOrigin = '0 0';
        this.viewport.style.position = 'absolute';
        this.viewport.style.left = '0px';
        this.viewport.style.top = '0px';
        
        this.updateTransform();
        
        // Mouse Down for drag-to-pan initialization
        this.container.addEventListener('mousedown', (e) => {
            // Only pan on left or middle mouse button
            if (e.button !== 0 && e.button !== 1) return;
            
            // Ignore if clicking a button, card, or connection handle
            if (e.target.closest('.canvas-node') || 
                e.target.closest('.neuron-circle-wrapper') || 
                e.target.closest('button') || 
                e.target.closest('input') ||
                e.target.closest('.connection-handle')) {
                return;
            }
            
            this.isPanning = true;
            this.startX = e.clientX - this.panX;
            this.startY = e.clientY - this.panY;
            this.container.style.cursor = 'grabbing';
            e.preventDefault();
        });
        
        // Mouse Move for drag translation updates
        window.addEventListener('mousemove', (e) => {
            if (!this.isPanning) return;
            this.panX = e.clientX - this.startX;
            this.panY = e.clientY - this.startY;
            this.updateTransform();
        });
        
        // Mouse Up for pan completion
        window.addEventListener('mouseup', () => {
            if (this.isPanning) {
                this.isPanning = false;
                this.container.style.cursor = 'grab';
            }
        });
        
        // Mouse Wheel for cursor-centered zoom translation
        this.container.addEventListener('wheel', (e) => {
            e.preventDefault();
            
            const rect = this.container.getBoundingClientRect();
            const mouseX = e.clientX - rect.left;
            const mouseY = e.clientY - rect.top;
            
            // Get mouse position relative to untransformed workspace origin
            const contentX = (mouseX - this.panX) / this.scale;
            const contentY = (mouseY - this.panY) / this.scale;
            
            // Zoom modifier
            const zoomFactor = 1.1;
            let nextScale = this.scale;
            if (e.deltaY < 0) {
                nextScale *= zoomFactor;
            } else {
                nextScale /= zoomFactor;
            }
            
            // Clamp scale values
            nextScale = Math.max(this.minScale, Math.min(this.maxScale, nextScale));
            
            // Adjust pan boundaries to focus directly under client cursor coordinate
            this.panX = mouseX - contentX * nextScale;
            this.panY = mouseY - contentY * nextScale;
            this.scale = nextScale;
            
            this.updateTransform();
        }, { passive: false });
    }
    
    updateTransform() {
        this.viewport.style.transform = `translate(${this.panX}px, ${this.panY}px) scale(${this.scale})`;
        if (this.onTransformChange) {
            this.onTransformChange({
                scale: this.scale,
                panX: this.panX,
                panY: this.panY
            });
        }
    }
    
    reset() {
        this.scale = 1.0;
        this.panX = 0;
        this.panY = 0;
        this.updateTransform();
    }
    
    fitToScreen(contentWidth, contentHeight) {
        const containerRect = this.container.getBoundingClientRect();
        const containerW = containerRect.width  || 800;
        const containerH = containerRect.height || 500;
        
        if (contentWidth <= 0 || contentHeight <= 0) return;
        
        const padding = 80;
        const scaleX = (containerW - padding) / contentWidth;
        const scaleY = (containerH - padding) / contentHeight;
        
        let nextScale = Math.min(scaleX, scaleY);
        nextScale = Math.max(this.minScale, Math.min(1.0, nextScale));
        
        this.scale = nextScale;
        // Centre the virtual canvas in the container
        this.panX = (containerW - contentWidth  * nextScale) / 2;
        this.panY = (containerH - contentHeight * nextScale) / 2;
        
        this.updateTransform();
    }
}
