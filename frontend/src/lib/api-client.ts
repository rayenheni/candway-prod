import { getApiBaseUrl } from '@/utils/domain-routing';

export class ApiClientError extends Error {
  status: number;
  data: unknown;

  constructor(message: string, status: number, data?: unknown) {
    super(message);
    this.name = 'ApiClientError';
    this.status = status;
    this.data = data;
  }
}

let memoryCsrfToken: string | null = null;

function getCookie(name: string): string | null {
  const prefix = `${name}=`;

  for (const part of document.cookie.split(';')) {
    const cookie = part.trim();

    if (cookie.startsWith(prefix)) {
      return decodeURIComponent(cookie.slice(prefix.length));
    }
  }

  return null;
}

async function parseResponse(response: Response): Promise<unknown> {
  const contentType = response.headers.get('content-type') || '';

  if (contentType.includes('application/json')) {
    try {
      return await response.json();
    } catch {
      return null;
    }
  }

  const text = await response.text();
  return text || null;
}

function getErrorMessage(data: unknown, status: number): string {
  if (typeof data === 'string' && data.trim()) return data;

  if (data && typeof data === 'object') {
    const value = data as Record<string, unknown>;

    if (typeof value.detail === 'string') return value.detail;

    if (Array.isArray(value.detail)) {
      return value.detail
        .map((item) => {
          if (typeof item === 'string') return item;
          if (item && typeof item === 'object') {
            const obj = item as Record<string, unknown>;
            return String(obj.msg || obj.message || 'Validation error');
          }
          return 'Validation error';
        })
        .join(', ');
    }

    if (typeof value.message === 'string') return value.message;
    if (typeof value.error === 'string') return value.error;
  }

  return `Request failed with status ${status}.`;
}

async function request<T>(
  path: string,
  options: RequestOptions = {},
): Promise<T> {
  const {
    skipCsrf = false,
    headers: providedHeaders,
    ...fetchOptions
  } = options;

  const apiBase = getApiBaseUrl();
  const requestUrl = path.startsWith('http://') || path.startsWith('https://')
    ? path
    : `${apiBase}${path}`;

  const method = (fetchOptions.method || 'GET').toUpperCase();
  const headers = new Headers(providedHeaders);

  if (!headers.has('Accept')) {
    headers.set('Accept', 'application/json');
  }

  if (
    fetchOptions.body !== undefined &&
    fetchOptions.body !== null &&
    typeof fetchOptions.body === 'string' &&
    !headers.has('Content-Type')
  ) {
    headers.set('Content-Type', 'application/json');
  }

  if (
    !skipCsrf &&
    ['POST', 'PUT', 'PATCH', 'DELETE'].includes(method)
  ) {
    const csrfToken = memoryCsrfToken || getCookie('csrf_token');

    if (csrfToken) {
      headers.set('X-CSRF-Token', csrfToken);
    }
  }

  let response = await fetch(requestUrl, {
    ...fetchOptions,
    method,
    headers,
    credentials: 'include',
  });

  const csrfHeader = response.headers.get('X-CSRF-Token') || response.headers.get('x-csrf-token');
  if (csrfHeader) {
    memoryCsrfToken = csrfHeader;
  }

  let data = await parseResponse(response);

  // CSRF tokens are time-limited HMAC tokens. If a mutation returns 403 CSRF error,
  // fetch a fresh token and retry exactly once.
  if (
    !skipCsrf &&
    ['POST', 'PUT', 'PATCH', 'DELETE'].includes(method) &&
    response.status === 403 &&
    typeof data === 'object' &&
    data !== null &&
    'detail' in data &&
    (data as Record<string, unknown>).detail ===
      'CSRF token validation failed'
  ) {
    const csrfResponse = await fetch(`${apiBase}/auth/me`, {
      method: 'GET',
      credentials: 'include',
      headers: {
        Accept: 'application/json',
      },
    });

    if (csrfResponse.ok) {
      const freshToken = csrfResponse.headers.get('X-CSRF-Token') || csrfResponse.headers.get('x-csrf-token');

      if (freshToken) {
        memoryCsrfToken = freshToken;
        headers.set('X-CSRF-Token', freshToken);

        response = await fetch(requestUrl, {
          ...fetchOptions,
          method,
          headers,
          credentials: 'include',
        });

        data = await parseResponse(response);
      }
    }
  }

if (!response.ok) {
    if (response.status === 402) {
      notifyInsufficientCredits(data);
    }

    throw new ApiClientError(
      getErrorMessage(data, response.status),
      response.status,
      data,
    );
  }

  return data as T;
}


export type InsufficientCreditsPayload = {
  message: string;
  upgradeUrl?: string;
};

type InsufficientCreditsListener =
  ((payload: InsufficientCreditsPayload) => void) | null;

let insufficientCreditsListener: InsufficientCreditsListener = null;

export function onInsufficientCredits(
  listener: InsufficientCreditsListener,
) {
  insufficientCreditsListener = listener;
}

function notifyInsufficientCredits(data: unknown) {
  if (!insufficientCreditsListener) return;

  const payload =
    data && typeof data === 'object'
      ? (data as Record<string, unknown>)
      : {};

  const message =
    typeof payload.message === 'string'
      ? payload.message
      : typeof payload.detail === 'string'
        ? payload.detail
        : 'You do not have enough credits to perform this action.';

  const upgradeUrl =
    typeof payload.upgrade_url === 'string'
      ? payload.upgrade_url
      : typeof payload.upgradeUrl === 'string'
        ? payload.upgradeUrl
        : '/dashboard';

  insufficientCreditsListener({
    message,
    upgradeUrl,
  });
}

export type RequestOptions = RequestInit & {
  skipCsrf?: boolean;
  params?: Record<string, unknown>;
  [key: string]: unknown;
};

const apiClient = {
  get<T = unknown>(path: string, options?: any) {
    return request<T>(path, {
      ...(options || {}),
      method: 'GET',
    });
  },

  getBlob(path: string, options?: any): Promise<Blob> {
    const apiBase = getApiBaseUrl();
    const requestUrl = path.startsWith('http://') || path.startsWith('https://')
      ? path
      : `${apiBase}${path}`;
    return fetch(requestUrl, {
      ...(options || {}),
      method: 'GET',
      credentials: 'include',
    }).then((res) => {
      if (!res.ok) throw new ApiClientError(`Failed to fetch blob: ${res.status}`, res.status);
      return res.blob();
    });
  },

  postBlob(path: string, body?: any, options?: any): Promise<Blob> {
    const apiBase = getApiBaseUrl();
    const requestUrl = path.startsWith('http://') || path.startsWith('https://')
      ? path
      : `${apiBase}${path}`;
    return fetch(requestUrl, {
      ...(options || {}),
      method: 'POST',
      body: body === undefined ? undefined : body instanceof FormData ? body : JSON.stringify(body),
      credentials: 'include',
      headers: {
        'Content-Type': 'application/json',
        ...((options && options.headers) || {}),
      },
    }).then((res) => {
      if (!res.ok) throw new ApiClientError(`Failed to fetch blob: ${res.status}`, res.status);
      return res.blob();
    });
  },

  upload<T = unknown>(path: string, body?: any, options?: any) {
    const formData = body instanceof FormData ? body : new FormData();
    return request<T>(path, {
      ...(options || {}),
      method: 'POST',
      body: formData,
    });
  },

  postFormData<T = unknown>(path: string, body?: any, options?: any) {
    const formData = body instanceof FormData ? body : new FormData();
    return request<T>(path, {
      ...(options || {}),
      method: 'POST',
      body: formData,
    });
  },

  post<T = unknown>(path: string, body?: any, options?: any) {
    return request<T>(path, {
      ...(options || {}),
      method: 'POST',
      body:
        body === undefined
          ? undefined
          : body instanceof FormData
            ? body
            : JSON.stringify(body),
    });
  },

  put<T = unknown>(path: string, body?: any, options?: any) {
    return request<T>(path, {
      ...(options || {}),
      method: 'PUT',
      body:
        body === undefined
          ? undefined
          : body instanceof FormData
            ? body
            : JSON.stringify(body),
    });
  },

  patch<T = unknown>(path: string, body?: any, options?: any) {
    return request<T>(path, {
      ...(options || {}),
      method: 'PATCH',
      body:
        body === undefined
          ? undefined
          : body instanceof FormData
            ? body
            : JSON.stringify(body),
    });
  },

  delete<T = unknown>(path: string, options?: any) {
    return request<T>(path, {
      ...(options || {}),
      method: 'DELETE',
    });
  },
};

export default apiClient;
