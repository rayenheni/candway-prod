import { useState, useEffect } from 'react';
import { useSearchParams } from 'react-router';
import { motion } from 'framer-motion';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/shared/components/ui/card';
import { Badge } from '@/shared/components/ui/badge';
import { Button } from '@/shared/components/ui/button';
import { Input } from '@/shared/components/ui/input';
import { customToast } from '@/shared/components/ui/toast';
import { useLanguage } from '@/contexts/language-context';
import apiClient from '@/lib/api-client';
import { FileSignature, CheckCircle2, XCircle, Clock, Loader2, DollarSign } from 'lucide-react';

interface OfferDetails {
  id: number;
  status: string;
  subject: string;
  body: string;
  salary: string;
  start_date: string;
  expires_at: string;
  responded_at: string;
  signed_at: string;
  job_title: string;
  company_name: string;
}

export default function CandidateEsignViewPage() {
  const { t } = useLanguage();
  const [searchParams] = useSearchParams();
  const offerId = searchParams.get('offer_id');
  const action = searchParams.get('action');

  const [signed, setSigned] = useState(false);
  const [loading, setLoading] = useState(false);
  const [signature, setSignature] = useState('');
  const [offerDetails, setOfferDetails] = useState<OfferDetails | null>(null);
  const [loadingDetails, setLoadingDetails] = useState(true);

  useEffect(() => {
    if (!offerId) { setLoadingDetails(false); return; }
    apiClient.get<any>(`/recruiter/offers/candidate/${offerId}`)
      .then(res => setOfferDetails(res))
      .catch(() => {})
      .finally(() => setLoadingDetails(false));
  }, [offerId]);

  const handleRespond = async (accept: boolean) => {
    if (accept && !signature.trim()) { customToast({ type: 'error', title: t('esign.signatureRequired'), message: t('esign.signatureRequiredMsg') }); return; }
    setLoading(true);
    try {
      await apiClient.post<{ success: boolean; status: string }>(
        `/recruiter/offers/respond/${offerId}?accept=${accept}`,
        accept ? { response_message: `Signed by ${signature}` } : {}
      );
      if (accept) setSigned(true);
      customToast({ type: 'success', title: accept ? t('esign.offerAccepted') : t('esign.offerDeclined'), message: accept ? t('esign.acceptedMsg') : t('esign.declineMsg') });
    } catch (err: any) {
      customToast({ type: 'error', title: t('cand.interviews.error'), message: err?.errors?.detail || err?.message || t('esign.failedResponse') });
    } finally { setLoading(false); }
  };

  if (!offerId) return <div className="text-center py-20 text-gray-400">{t('esign.noOfferSpecified')}</div>;

  if (loadingDetails) {
    return (
      <div className="flex items-center justify-center py-20">
        <Loader2 className="h-8 w-8 text-violet-500 animate-spin" />
      </div>
    );
  }

  if (signed) return (
    <motion.div initial={{ scale: 0.9, opacity: 0 }} animate={{ scale: 1, opacity: 1 }} className="max-w-lg mx-auto">
      <Card className="glass-panel border-emerald-200/50 text-center py-12">
        <div className="flex justify-center mb-4"><div className="h-16 w-16 rounded-full bg-emerald-100 dark:bg-emerald-500/20 flex items-center justify-center"><CheckCircle2 className="h-8 w-8 text-emerald-600" /></div></div>
        <CardTitle className="text-xl">{t('esign.offerAccepted')}</CardTitle>
        <CardDescription className="mt-2">{t('esign.confirmationMsg')}</CardDescription>
      </Card>
    </motion.div>
  );

  return (
    <div className="max-w-2xl mx-auto space-y-6">
      <div className="flex items-center gap-3">
        <h1 className="text-2xl font-extrabold text-gray-900 dark:text-white">{t('esign.title')}</h1>
        <Badge variant="warning" size="sm"><Clock className="h-3 w-3" /> {t('common.pending')}</Badge>
      </div>

      {offerDetails && (
        <Card className="border-purple-100 dark:border-purple-500/15 bg-white dark:bg-white/[0.03]">
          <CardContent className="pt-6 space-y-4">
            <div className="flex items-center gap-3 mb-2">
              <div className="h-11 w-11 rounded-xl bg-gradient-to-br from-violet-500 to-purple-600 flex items-center justify-center text-white font-bold text-sm shrink-0">
                {offerDetails.company_name?.[0] || 'C'}
              </div>
              <div>
                <h2 className="text-lg font-extrabold text-gray-900 dark:text-white">{offerDetails.job_title || t('esign.jobOffer')}</h2>
                <p className="text-sm text-purple-600 dark:text-purple-400 font-bold">{offerDetails.company_name || t('esign.company')}</p>
              </div>
            </div>
            <div className="flex flex-wrap gap-4 text-sm text-gray-600 dark:text-gray-300">
              {offerDetails.salary && (
                <span className="flex items-center gap-1"><DollarSign className="h-4 w-4 text-emerald-500" />{offerDetails.salary}</span>
              )}
              {offerDetails.start_date && (
                <span className="flex items-center gap-1"><Clock className="h-4 w-4 text-blue-500" />{t('esign.starts')} {offerDetails.start_date}</span>
              )}
              {offerDetails.expires_at && (
                <span className="flex items-center gap-1 text-amber-600"><Clock className="h-4 w-4" />{t('esign.expires')} {offerDetails.expires_at}</span>
              )}
            </div>
            {offerDetails.subject && (
              <div className="text-sm font-semibold text-gray-800 dark:text-gray-200">{offerDetails.subject}</div>
            )}
          </CardContent>
        </Card>
      )}

      <Card className="glass-panel border-purple-200/50">
        <CardHeader><CardTitle>{t('esign.offer')} #{offerId}</CardTitle></CardHeader>
        <CardContent>
          <p className="text-sm text-gray-600 dark:text-gray-300 mb-4">
            {t('esign.receivedMsg')}
          </p>
          {action === 'accept' ? (
            <div className="space-y-4">
              <Input placeholder={t('esign.signPlaceholder')} value={signature} onChange={e => setSignature(e.target.value)} className="font-signature text-lg" />
              <p className="text-xs text-gray-400">{t('esign.legalHint')}</p>
              <div className="flex gap-3">
                <Button variant="primary" leftIcon={loading ? <Loader2 className="h-4 w-4 animate-spin" /> : <FileSignature className="h-4 w-4" />} onClick={() => handleRespond(true)} disabled={loading}>{loading ? t('esign.processing') : t('esign.acceptSign')}</Button>
                <Button variant="outline" leftIcon={<XCircle className="h-4 w-4" />} onClick={() => handleRespond(false)} disabled={loading}>{t('esign.decline')}</Button>
              </div>
            </div>
          ) : (
            <div className="space-y-4">
              <p className="text-sm text-amber-600 dark:text-amber-400">{t('esign.declineNotice')}</p>
              <div className="flex gap-3">
                <Button variant="outline" leftIcon={<XCircle className="h-4 w-4" />} onClick={() => handleRespond(false)} disabled={loading}>{loading ? t('esign.processing') : t('esign.confirmDecline')}</Button>
                <Button variant="ghost" onClick={() => window.history.back()}>{t('esign.goBack')}</Button>
              </div>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}