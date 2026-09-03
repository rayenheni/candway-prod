// ============================================================
// Coming Soon / Under Construction Shell - Candway
// ============================================================

import { motion } from 'framer-motion';
import { Card, CardContent } from '@/shared/components/ui/card';
import { Button } from '@/shared/components/ui/button';
import { useNavigate } from 'react-router';
import { Construction, ArrowLeft, Sparkles } from 'lucide-react';

export default function ComingSoonPage({ title = "Module Under Construction" }: { title?: string }) {
  const navigate = useNavigate();

  return (
    <div className="flex flex-col items-center justify-center min-h-[70vh] px-4 text-center">
      <motion.div
        initial={{ opacity: 0, scale: 0.9 }}
        animate={{ opacity: 1, scale: 1 }}
        transition={{ duration: 0.5 }}
        className="w-full max-w-md"
      >
        <Card className="p-8 glass-panel shadow-xl shadow-purple-500/10 border-purple-200/60 dark:border-purple-500/20 relative overflow-hidden">
          <div className="absolute top-0 right-0 w-32 h-32 bg-purple-400/20 rounded-full blur-2xl -z-10" />
          <div className="absolute bottom-0 left-0 w-32 h-32 bg-indigo-400/20 rounded-full blur-2xl -z-10" />
          
          <CardContent className="flex flex-col items-center p-0">
            <div className="h-20 w-20 rounded-3xl bg-gradient-to-tr from-purple-100 to-white dark:from-purple-900/40 dark:to-indigo-900/40 flex items-center justify-center shadow-inner mb-6 border border-purple-200/50 dark:border-white/10 relative">
              <Construction className="h-10 w-10 text-purple-600 dark:text-purple-400" />
              <div className="absolute -top-2 -right-2">
                <Sparkles className="h-6 w-6 text-amber-500 animate-pulse" />
              </div>
            </div>
            
            <h1 className="text-2xl font-black text-gray-900 dark:text-white mb-3">
              {title}
            </h1>
            <p className="text-sm font-medium text-gray-600 dark:text-gray-400 mb-8 leading-relaxed">
              This module of the Candway Tunisia platform is currently being ported to our new React architecture. Check back soon!
            </p>
            
            <Button 
              variant="primary" 
              className="w-full font-bold shadow-md shadow-purple-500/20" 
              leftIcon={<ArrowLeft className="h-4 w-4" />}
              onClick={() => navigate(-1)}
            >
              Go Back
            </Button>
          </CardContent>
        </Card>
      </motion.div>
    </div>
  );
}
