import { motion } from "framer-motion";
import { X, Trash2, ExternalLink } from "lucide-react";

export interface SavedScout {
  id: string;
  timestamp: number;
  job_title: string;
  results: Record<string, unknown>;
}

export function SavedResultsModal({
  isOpen,
  onClose,
  savedScouts,
  onLoad,
  onDelete
}: {
  isOpen: boolean;
  onClose: () => void;
  savedScouts: SavedScout[];
  onLoad: (results: Record<string, unknown>) => void;
  onDelete: (id: string) => void;
}) {
  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
      <motion.div 
        initial={{ opacity: 0, scale: 0.95 }}
        animate={{ opacity: 1, scale: 1 }}
        className="bg-[#1A1A1A]/90 backdrop-blur-xl w-full max-w-2xl rounded-xl shadow-2xl overflow-hidden border border-[#333] flex flex-col max-h-[80vh]"
      >
        <div className="flex items-center justify-between p-5 border-b border-[#333]">
          <h2 className="text-[18px] font-bold text-white">Saved Scouts</h2>
          <button onClick={onClose} className="p-2 hover:bg-[#333] rounded-full transition-colors">
            <X className="w-5 h-5 text-[#A0A0A0]" />
          </button>
        </div>
        
        <div className="p-5 overflow-y-auto flex-1">
          {savedScouts.length === 0 ? (
            <div className="text-center py-10 text-[#777]">
              <p className="text-[14px]">No saved scouts yet.</p>
              <p className="text-[13px] mt-1">Run a scout and click &quot;Save Result&quot; to see it here.</p>
            </div>
          ) : (
            <div className="space-y-3">
              {savedScouts.map(scout => (
                <div key={scout.id} className="flex items-center justify-between p-4 border border-[#333] rounded-lg bg-[#0A0A0A]/50 hover:bg-[#1A3A22]/20 transition-colors">
                  <div>
                    <h3 className="font-semibold text-white text-[15px] truncate max-w-[300px]">{scout.job_title}</h3>
                    <p className="text-[12px] text-[#A0A0A0] mt-0.5">
                      {new Date(scout.timestamp).toLocaleDateString()} at {new Date(scout.timestamp).toLocaleTimeString()}
                    </p>
                  </div>
                  <div className="flex items-center gap-2">
                    <button 
                      onClick={() => onLoad(scout.results)}
                      className="flex items-center gap-1.5 px-3 py-1.5 bg-[#4A9D5F] text-white text-[13px] font-semibold rounded-md hover:bg-[#2D7D3E] transition-colors"
                    >
                      <ExternalLink className="w-4 h-4" /> Load
                    </button>
                    <button 
                      onClick={() => onDelete(scout.id)}
                      className="p-1.5 text-[#A0A0A0] hover:text-red-400 hover:bg-red-500/10 rounded-md transition-colors"
                      title="Delete saved scout"
                    >
                      <Trash2 className="w-4 h-4" />
                    </button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </motion.div>
    </div>
  );
}
