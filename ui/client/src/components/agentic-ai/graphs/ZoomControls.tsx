import { ZoomIn, ZoomOut, Maximize2 } from "lucide-react";

interface ZoomControlsProps {
  onZoomIn: () => void;
  onZoomOut: () => void;
  onFitToView: () => void;
}

export function ZoomControls({
  onZoomIn,
  onZoomOut,
  onFitToView,
}: ZoomControlsProps) {
  return (
    <div className="absolute bottom-3 right-3 z-40 flex flex-col rounded-lg bg-black/70 backdrop-blur-sm">
      <button
        type="button"
        className="flex items-center justify-center w-8 h-8 text-white/80 hover:text-white hover:bg-white/10 rounded-t-lg transition-colors"
        onClick={onZoomIn}
        aria-label="Zoom in"
      >
        <ZoomIn size={16} />
      </button>
      <button
        type="button"
        className="flex items-center justify-center w-8 h-8 text-white/80 hover:text-white hover:bg-white/10 transition-colors"
        onClick={onZoomOut}
        aria-label="Zoom out"
      >
        <ZoomOut size={16} />
      </button>
      <button
        type="button"
        className="flex items-center justify-center w-8 h-8 text-white/80 hover:text-white hover:bg-white/10 rounded-b-lg transition-colors"
        onClick={onFitToView}
        aria-label="Fit to view"
      >
        <Maximize2 size={16} />
      </button>
    </div>
  );
}
