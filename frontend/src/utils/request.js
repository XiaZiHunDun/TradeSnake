// 带有重试机制的fetch封装

const DEFAULT_RETRIES = 3
const DEFAULT_DELAY = 1000

/**
 * 带重试的fetch请求
 */
export async function fetchWithRetry(url, options = {}, retries = DEFAULT_RETRIES, delay = DEFAULT_DELAY) {
  const { retryCondition, ...fetchOptions } = options

  try {
    const response = await fetch(url, fetchOptions)

    // 如果请求失败且满足重试条件
    if (!response.ok && retryCondition && retryCondition(response)) {
      if (retries > 0) {
        await new Promise(resolve => setTimeout(resolve, delay))
        return fetchWithRetry(url, options, retries - 1, delay * 2)
      }
    }

    return response
  } catch (error) {
    if (retries > 0) {
      await new Promise(resolve => setTimeout(resolve, delay))
      return fetchWithRetry(url, options, retries - 1, delay * 2)
    }
    throw error
  }
}

/**
 * 检查响应是否需要重试
 */
export const shouldRetryOnServerError = (response) => {
  return response.status >= 500
}

/**
 * 检查网络错误
 */
export const shouldRetryOnNetworkError = (error) => {
  return error.message === 'Failed to fetch' || error.message === 'Network request failed'
}
