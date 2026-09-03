import apiClient from '@/lib/api-client';

/**
 * Subscription service for the recruiter billing page.
 *
 * Backend contract (recruiter_settings.py):
 *  GET  /recruiter/subscription/status        → SubscriptionStatus
 *  GET  /recruiter/subscription/plans         → SubscriptionPlan[]
 *  POST /recruiter/subscription/upgrade       → multipart/form-data: plan=<slug>, proof_file?=<file>
 *  GET  /recruiter/subscription/invoices      → InvoiceResponse[]
 *  GET  /recruiter/subscription/invoices/{id}/download → PDF blob
 */
export const subscriptionService = {
  /** Fetch current subscription status, tier, usage and limits. */
  getStatus: () =>
    apiClient.get<any>('/recruiter/subscription/status'),

  /** Fetch all active recruiter subscription plans from the DB. */
  getPlans: () =>
    apiClient.get<any[]>('/recruiter/subscription/plans'),

  /**
   * Submit a manual bank-transfer upgrade request.
   *
   * The backend expects multipart/form-data with:
   *   - plan: string  (the plan slug, e.g. "pro_recruiter")
   *   - proof_file?: File  (optional payment receipt — PNG, JPG, or PDF, max 5 MB)
   */
  upgradePlan: (planSlug: string, proofFile?: File) => {
    const form = new FormData();
    form.append('plan', planSlug);
    if (proofFile) {
      form.append('proof_file', proofFile);
    }
    return apiClient.postFormData<any>('/recruiter/subscription/upgrade', form);
  },

  /** Fetch the list of invoices for this company. */
  listInvoices: () =>
    apiClient.get<any[]>('/recruiter/subscription/invoices'),

  /** Fetch manual bank-transfer payment instructions from platform config. */
  getPaymentConfig: () =>
    apiClient.get<Record<string, string>>('/recruiter/subscription/payment-config'),

  /**
   * Download an invoice PDF and trigger a browser save dialog.
   *
   * @param invoiceId   - DB invoice ID
   * @param invoiceNumber - Used as the suggested filename
   */
  downloadInvoice: async (invoiceId: number, invoiceNumber: string) => {
    const blob = await apiClient.getBlob(
      `/recruiter/subscription/invoices/${invoiceId}/download`,
    );
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `Invoice_${invoiceNumber}.pdf`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  },
};
