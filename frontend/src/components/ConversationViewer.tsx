import { motion, AnimatePresence } from "framer-motion";

export interface ConversationMessage {
  role: "recruiter" | "candidate" | string;
  turn: number;
  message: string;
}

interface ConversationViewerProps {
  transcript: ConversationMessage[];
  isOpen: boolean;
  onClose: () => void;
}

export function ConversationViewer({ transcript, isOpen, onClose }: ConversationViewerProps) {
  return (
    <AnimatePresence>
      {isOpen && (
        <motion.div
          initial={{ height: 0, opacity: 0 }}
          animate={{ height: "auto", opacity: 1 }}
          exit={{ height: 0, opacity: 0 }}
          transition={{ duration: 0.3, ease: "easeOut" }}
          className="overflow-hidden mt-4 border-t border-border"
        >
          <div className="pt-4 pb-2">
            <div className="flex items-center justify-between mb-4">
              <h4 className="text-[14px] font-semibold text-foreground uppercase tracking-wider">Conversation Transcript</h4>
              <button 
                onClick={onClose}
                className="text-[13px] text-primary font-medium hover:underline focus:outline-none"
              >
                Close
              </button>
            </div>
            
            <div className="space-y-4 max-h-[500px] overflow-y-auto custom-scrollbar pr-2">
              {transcript.map((msg, index) => {
                const isRecruiter = msg.role === "recruiter";
                
                // Add turn labels before recruiter messages
                const showTurnLabel = isRecruiter;

                return (
                  <div key={index} className="flex flex-col">
                    {showTurnLabel && (
                      <div className="text-center my-3">
                        <span className="text-[12px] font-bold uppercase text-accent tracking-widest bg-card px-2">
                          [Turn {msg.turn}]
                        </span>
                      </div>
                    )}
                    
                    <div 
                      className={`flex flex-col text-[14px] p-3 rounded-md max-w-[90%] leading-[1.6] ${
                        isRecruiter 
                          ? "bg-secondary border-l-2 border-primary text-foreground self-start" 
                          : "bg-card border border-border text-foreground self-end"
                      }`}
                    >
                      <span className="font-semibold text-[13px] mb-1 opacity-80">
                        {isRecruiter ? "Recruiter" : "Candidate"}
                      </span>
                      <span>{msg.message}</span>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
