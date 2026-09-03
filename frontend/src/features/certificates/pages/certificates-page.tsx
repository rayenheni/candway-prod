// ============================================================
// Certificates Page - Candway Platform
// ============================================================

import { motion } from 'framer-motion';
import { Card } from '@/shared/components/ui/card';
import { Badge } from '@/shared/components/ui/badge';
import { Button } from '@/shared/components/ui/button';
import { cn } from '@/utils/cn';
import {
  Award,
  Download,
  ExternalLink,
  Calendar,
  CheckCircle2,
} from 'lucide-react';

const certificates = [
  {
    id: '1',
    course: 'TypeScript Masterclass',
    issuer: 'Candway Academy',
    issuedAt: 'Jan 12, 2025',
    expiresAt: 'Jan 12, 2028',
    credentialId: 'CND-TS-2025-001',
    verified: true,
    color: 'from-blue-500 to-indigo-600',
  },
  {
    id: '2',
    course: 'Advanced React Patterns',
    issuer: 'Candway Academy',
    issuedAt: 'Dec 28, 2024',
    expiresAt: 'Dec 28, 2027',
    credentialId: 'CND-REACT-2024-047',
    verified: true,
    color: 'from-cyan-500 to-blue-500',
  },
  {
    id: '3',
    course: 'AWS Cloud Practitioner',
    issuer: 'Amazon Web Services',
    issuedAt: 'Nov 15, 2024',
    expiresAt: 'Nov 15, 2027',
    credentialId: 'AWS-CP-2024-89234',
    verified: true,
    color: 'from-amber-500 to-orange-500',
  },
];

export default function CertificatesPage() {
  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 dark:text-white">Certificates</h1>
          <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">
            Your earned certificates and credentials
          </p>
        </div>
        <Button variant="outline" leftIcon={<ExternalLink className="h-4 w-4" />}>Share Profile</Button>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-6">
        {certificates.map((cert, i) => (
          <motion.div
            key={cert.id}
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.4, delay: i * 0.1 }}
          >
            <Card className="h-full overflow-hidden">
              {/* Certificate Header */}
              <div className={cn('h-2 bg-gradient-to-r', cert.color)} />
              <div className="p-6">
                <div className="flex items-center justify-between mb-4">
                  <div className={cn('flex h-14 w-14 items-center justify-center rounded-2xl bg-gradient-to-br', cert.color)}>
                    <Award className="h-7 w-7 text-white" />
                  </div>
                  {cert.verified && (
                    <Badge variant="success" size="sm">
                      <CheckCircle2 className="h-3 w-3 mr-1" />
                      Verified
                    </Badge>
                  )}
                </div>

                <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-1">{cert.course}</h3>
                <p className="text-sm text-gray-500 dark:text-gray-400 mb-4">Issued by {cert.issuer}</p>

                <div className="space-y-2 mb-4">
                  <div className="flex items-center gap-2 text-sm text-gray-600 dark:text-gray-400">
                    <Calendar className="h-4 w-4" />
                    Issued: {cert.issuedAt}
                  </div>
                  <div className="flex items-center gap-2 text-sm text-gray-600 dark:text-gray-400">
                    <Calendar className="h-4 w-4" />
                    Expires: {cert.expiresAt}
                  </div>
                </div>

                <div className="text-xs text-gray-400 dark:text-gray-500 mb-4">
                  Credential ID: {cert.credentialId}
                </div>

                <div className="flex gap-2">
                  <Button variant="primary" size="sm" className="flex-1" leftIcon={<Download className="h-4 w-4" />}>
                    Download
                  </Button>
                  <Button variant="outline" size="sm" className="flex-1" leftIcon={<ExternalLink className="h-4 w-4" />}>
                    Share
                  </Button>
                </div>
              </div>
            </Card>
          </motion.div>
        ))}
      </div>
    </div>
  );
}
