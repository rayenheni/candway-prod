import { useEffect } from 'react';
import { useLanguage } from '@/contexts/language-context';

const SECTIONS = [
  {
    title: '1. Acceptance of Terms',
    body: 'By accessing or using Candway ("the Service"), you agree to be bound by these Terms of Service. If you do not agree to these terms, you may not use the Service.',
  },
  {
    title: '2. Accounts',
    body: 'You must provide accurate and complete information when creating an account. You are responsible for maintaining the confidentiality of your credentials and for all activity that occurs under your account. Notify us immediately of any unauthorized use.',
  },
  {
    title: '3. Acceptable Use',
    body: 'You agree not to misuse the Service, including: attempting to access other users\' data, reverse-engineering the platform, interfering with platform operation, uploading malicious content, using the Service for unlawful purposes, or attempting to bypass security controls.',
  },
  {
    title: '4. AI-Generated Content',
    body: 'Candway uses AI to provide insights, scores, recommendations, and content generation. AI outputs are provided "as is" for informational purposes and may contain errors. You are responsible for making final hiring and career decisions. We continually validate and improve our AI systems.',
  },
  {
    title: '5. Subscriptions and Payments',
    body: 'Certain features require a paid subscription. Subscription fees are billed in advance and are non-refundable except as required by law. Plans may be upgraded, downgraded, or canceled according to the terms presented at purchase. Company subscriptions are governed by the number of seats purchased.',
  },
  {
    title: '6. Intellectual Property',
    body: 'The Service, including its software, design, logos, and content, is owned by Candway and protected by intellectual property laws. You retain ownership of the content you upload. You grant us a license to host and process your content solely to provide the Service.',
  },
  {
    title: '7. Termination',
    body: 'We may suspend or terminate your account if you violate these Terms. You may delete your account at any time. Upon termination, your right to use the Service ceases immediately.',
  },
  {
    title: '8. Disclaimers',
    body: 'The Service is provided "as is" without warranties of any kind, whether express or implied. We do not warrant that the Service will be uninterrupted, error-free, or free of harmful components.',
  },
  {
    title: '9. Limitation of Liability',
    body: 'To the maximum extent permitted by law, Candway shall not be liable for any indirect, incidental, special, consequential, or punitive damages, or any loss of profits or revenues, whether incurred directly or indirectly, arising from your use of the Service.',
  },
  {
    title: '10. Changes to Terms',
    body: 'We may update these Terms from time to time. We will notify you of material changes. Continued use of the Service after changes constitutes acceptance of the revised Terms.',
  },
  {
    title: '11. Contact',
    body: 'For questions about these Terms, contact us at legal@candway.com.',
  },
];

export default function TermsPage() {
  const { t } = useLanguage();
  useEffect(() => {
    document.title = t('marketing.terms.documentTitle');
  }, []);

  return (
    <div className="max-w-3xl mx-auto">
      <h1 className="text-4xl font-black tracking-tight text-gray-950 dark:text-white mb-4">{t('marketing.terms.title')}</h1>
      <p className="text-sm text-gray-500 dark:text-slate-400 mb-10">{t('marketing.terms.lastUpdated')}</p>
      <p className="text-gray-600 dark:text-slate-300 leading-relaxed mb-10">
        {t('marketing.terms.intro')}
      </p>
      <div className="space-y-8">
        {SECTIONS.map((section) => (
          <div key={section.title}>
            <h2 className="text-lg font-bold text-gray-900 dark:text-white mb-2">{section.title}</h2>
            <p className="text-gray-600 dark:text-slate-300 leading-relaxed">{section.body}</p>
          </div>
        ))}
      </div>
    </div>
  );
}
