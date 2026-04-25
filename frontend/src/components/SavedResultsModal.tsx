import { motion } from "framer-motion";
import { X, Trash2, ExternalLink } from "lucide-react";

export interface SavedScout {
  id: string;
  timestamp: number;
  job_title: string;
  results: any;
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
  onLoad: (results: any) => void;
  onDelete: (id: string) => void;
}) {
  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
      <motion.div 
        initial={{ opacity: 0, scale: 0.95 }}
        animate={{ opacity: 1, scale: 1 }}
        className="bg-card w-full max-w-2xl rounded-xl shadow-xl overflow-hidden border border-border flex flex-col max-h-[80vh]"
      >
        <div className="flex items-center justify-between p-5 border-b border-border">
          <h2 className="text-xl font-semibold text-foreground">Saved Scouts</h2>
          <button onClick={onClose} className="p-2 hover:bg-secondary rounded-full">
            <X className="w-5 h-5 text-muted-foreground" />
          </button>
        </div>
        
        <div className="p-5 overflow-y-auto flex-1">
          {savedScouts.length === 0 ? (
            <div className="text-center py-10 text-muted-foreground">
              <p>No saved scouts yet.</p>
              <p className="text-sm mt-1">Run a scout and click "Save Result" to see it here.</p>
            </div>
          ) : (
            <div className="space-y-3">
              {savedScouts.map(scout => (
                <div key={scout.id} className="flex items-center justify-between p-4 border border-border rounded-lg bg-secondary/30 hover:bg-secondary/50 transition-colors">
                  <div>
                    <h3 className="font-semibold text-foreground text-base truncate max-w-[300px]">{scout.job_title}</h3>
                    <p className="text-sm text-muted-foreground">
                      {new Date(scout.timestamp).toLocaleDateString()} at {new Date(scout.timestamp).toLocaleTimeString()}
                    </p>
                  </div>
                  <div className="flex items-center gap-2">
                    <button 
                      onClick={() => onLoad(scout.results)}
                      className="flex items-center gap-1.5 px-3 py-1.5 bg-primary text-primary-foreground text-sm font-medium rounded-md hover:bg-primary/90"
                    >
                      <ExternalLink className="w-4 h-4" /> Load
                    </button>
                    <button 
                      onClick={() => onDelete(scout.id)}
                      className="p-1.5 text-destructive hover:bg-destructive/10 rounded-md"
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
