import { useEffect } from 'react';
import { useLanguage } from '@/contexts/language-context';

const SECTIONS = [
  {
    title: '1. Information We Collect',
    body: 'We collect information you provide directly, including your name, email address, phone number, profile details, and any documents you upload such as CVs. We also collect usage data including pages visited, features used, and AI interaction logs to improve our platform.',
  },
  {
    title: '2. How We Use Your Information',
    body: 'We use your information to provide and improve our recruitment platform, match candidates with opportunities, generate AI-powered insights and recommendations, process payments, send service notifications, and comply with legal obligations. AI analysis is performed on anonymized or masked data wherever possible.',
  },
  {
    title: '3. AI and Data Processing',
    body: 'Candway uses AI to analyze CVs, score candidates, generate interview questions, and provide career guidance. Personal data sent to AI providers is masked and anonymized before processing. We never sell your personal data. AI-generated outputs are validated and auditable.',
  },
  {
    title: '4. Data Sharing',
    body: 'We share your information only with service providers who help us operate the platform (hosting, email delivery, payment processing, AI providers), and with recruiters or organizations when you apply for a role through the platform. We do not sell personal data to third parties.',
  },
  {
    title: '5. Data Retention and Deletion',
    body: 'We retain your data only as long as necessary to provide our services or as required by law. You may request deletion of your account and personal data at any time. Upon request, we will erase your personal data from our systems within 30 days, subject to legal retention requirements.',
  },
  {
    title: '6. Your Rights',
    body: 'You have the right to access, correct, export, and delete your personal data. You may also object to certain processing activities. To exercise these rights, contact our support team or use the GDPR export and erasure features available in your account settings.',
  },
  {
    title: '7. Security',
    body: 'We implement industry-standard security measures including encryption in transit and at rest, access controls, multi-tenant isolation, and continuous security testing to protect your data. While we work hard to protect your information, no method of transmission or storage is 100% secure.',
  },
  {
    title: '8. Cookies and Tracking',
    body: 'We use cookies and similar technologies to maintain your session, remember your preferences, and understand how the platform is used. You can control cookies through your browser settings.',
  },
  {
    title: '9. Contact',
    body: 'If you have questions about this Privacy Policy or our data practices, contact us at privacy@candway.com.',
  },
];

export default function PrivacyPage() {
  const { t } = useLanguage();
  useEffect(() => {
    document.title = t('marketing.privacy.documentTitle');
  }, []);

  return (
    <div className="max-w-3xl mx-auto">
      <h1 className="text-4xl font-black tracking-tight text-gray-950 dark:text-white mb-4">{t('marketing.privacy.title')}</h1>
      <p className="text-sm text-gray-500 dark:text-slate-400 mb-10">{t('marketing.privacy.lastUpdated')}</p>
      <p className="text-gray-600 dark:text-slate-300 leading-relaxed mb-10">
        {t('marketing.privacy.intro')}
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
