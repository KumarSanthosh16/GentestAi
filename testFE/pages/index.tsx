import { useState, useEffect } from 'react';
import Head from 'next/head';
import axios from 'axios';

interface CrawlRequest {
  url: string;
  max_pages: number;
  max_depth: number;
  include_external: boolean;
}

interface JobStatus {
  job_id: string;
  status: 'queued' | 'in_progress' | 'completed' | 'failed';
  pages_crawled: number;
  total_pages?: number;
  test_cases_generated: number;
}

interface TestCase {
  id: string;
  url: string;
  element_type: string;
  xpath: string;
  test_type: string;
  description: string;
}

interface PageResult {
  url: string;
  title: string;
  test_cases: TestCase[];
}

interface CrawlResults {
  [pageUrl: string]: PageResult;
}

export default function Home() {
  const [url, setUrl] = useState<string>('');
  const [maxPages, setMaxPages] = useState<number>(10);
  // const [maxDepth, setMaxDepth] = useState<number>(3);
  // const [includeExternal, setIncludeExternal] = useState<boolean>(false);
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [activeJobId, setActiveJobId] = useState<string | null>(null);
  const [jobStatus, setJobStatus] = useState<JobStatus | null>(null);
  const [results, setResults] = useState<CrawlResults | null>(null);
  const [selectedPage, setSelectedPage] = useState<string | null>(null);
  const [error, setError] = useState<string>('');

  const API_BASE_URL = 'http://localhost:8000';

  useEffect(() => {
    let intervalId: NodeJS.Timeout | undefined;

    if (
      activeJobId &&
      jobStatus?.status !== 'completed' &&
      jobStatus?.status !== 'failed'
    ) {
      intervalId = setInterval(async () => {
        try {
          const response = await axios.get<JobStatus>(
            `${API_BASE_URL}/api/status/${activeJobId}`
          );
          setJobStatus(response.data);

          if (response.data.status === 'completed') {
            if (intervalId) clearInterval(intervalId);
            fetchResults();
          } else if (response.data.status === 'failed') {
            if (intervalId) clearInterval(intervalId);
            setError('Job failed. Please try again.');
          }
        } catch (error) {
          console.error('Error fetching job status:', error);
          if (intervalId) clearInterval(intervalId);
          setError('Failed to get job status. Please try again.');
        }
      }, 2000);
    }

    return () => {
      if (intervalId) clearInterval(intervalId);
    };
  }, [activeJobId, jobStatus]);

  const startCrawl = async (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    setError('');
    setResults(null);
    setSelectedPage(null);

    if (!url) {
      setError('Please enter a URL');
      return;
    }

    try {
      setIsLoading(true);

      const payload: CrawlRequest = {
        url,
        max_pages: maxPages,
        max_depth: 3,
        include_external: false,
      };

      const response = await axios.post<JobStatus>(
        `${API_BASE_URL}/api/crawl`,
        payload
      );

      setActiveJobId(response.data.job_id);
      setJobStatus(response.data);
    } catch (error) {
      console.error('Error starting crawl:', error);
      setError('Failed to start crawl. Please check the URL and try again.');
    } finally {
      setIsLoading(false);
    }
  };

  const fetchResults = async () => {
    if (!activeJobId) return;

    try {
      const response = await axios.get<CrawlResults>(
        `${API_BASE_URL}/api/results/${activeJobId}`
      );
      setResults(response.data);

      const pages = Object.keys(response.data);
      if (pages.length > 0) {
        setSelectedPage(pages[0]);
      }
    } catch (error) {
      console.error('Error fetching results:', error);
      setError('Failed to fetch results. Please try again.');
    }
  };

  return (
    <div className='min-h-screen bg-gray-50'>
      <Head>
        <title>Web Crawler & Test Case Generator</title>
        <meta name='description' content='Generate test cases from web pages' />
        <link rel='icon' href='/favicon.ico' />
      </Head>

      <main className='container mx-auto px-4 py-8'>
        <h1 className='text-3xl font-bold text-center mb-8'>
          Web Crawler & Test Case Generator
        </h1>

        <div className='bg-white p-6 rounded-lg shadow-md mb-8'>
          <form onSubmit={startCrawl} className='flex gap-5 items-center'>
            <div className='grid grid-cols-1 md:grid-cols-2 items-center justify-center gap-6 w-full'>
              <div className='mb-4'>
                <label
                  htmlFor='url'
                  className='block text-sm font-medium text-gray-700 mb-1'
                >
                  Website URL
                </label>
                <input
                  type='url'
                  id='url'
                  value={url}
                  onChange={(e) => setUrl(e.target.value)}
                  placeholder='https://example.com'
                  className='w-full px-4 py-2 border border-gray-300 rounded-md focus:ring-blue-500 focus:border-blue-500'
                  required
                />
              </div>

              <div className='grid grid-cols-1 gap-4 mb-4'>
                <div>
                  <label
                    htmlFor='maxPages'
                    className='block text-sm font-medium text-gray-700 mb-1'
                  >
                    Max Pages
                  </label>
                  <input
                    type='number'
                    id='maxPages'
                    value={maxPages}
                    onChange={(e) => setMaxPages(parseInt(e.target.value))}
                    min='1'
                    max='50'
                    className='w-full px-4 py-2 border border-gray-300 rounded-md focus:ring-blue-500 focus:border-blue-500'
                  />
                </div>

                {/* <div className='hidden'>
                  <label
                    htmlFor='maxDepth'
                    className='block text-sm font-medium text-gray-700 mb-1'
                  >
                    Max Depth
                  </label>
                  <input
                    type='number'
                    id='maxDepth'
                    value={maxDepth}
                    onChange={(e) => setMaxDepth(parseInt(e.target.value))}
                    min='1'
                    max='10'
                    className='w-full px-4 py-2 border border-gray-300 rounded-md focus:ring-blue-500 focus:border-blue-500'
                  />
                </div> */}

                {/* <div className='items-center mt-8 hidden'>
                  <input
                    type='checkbox'
                    id='includeExternal'
                    checked={includeExternal}
                    onChange={(e) => setIncludeExternal(e.target.checked)}
                    className='h-4 w-4 text-blue-600 border-gray-300 rounded focus:ring-blue-500'
                  />
                  <label
                    htmlFor='includeExternal'
                    className='ml-2 text-sm text-gray-700'
                  >
                    Include External Links
                  </label>
                </div> */}
              </div>
            </div>
            <button
              type='submit'
              disabled={isLoading}
              className='w-1/4 bg-blue-600 hover:bg-blue-700 text-white font-medium py-2 px-4 rounded-md focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500 disabled:opacity-50'
            >
              {isLoading ? 'Starting Crawl...' : 'Start Crawl'}
            </button>
          </form>
        </div>

        {error && (
          <div className='bg-red-100 border border-red-400 text-red-700 px-4 py-3 rounded mb-6'>
            {error}
          </div>
        )}

        {jobStatus && jobStatus.status !== 'completed' && (
          <div className='bg-white p-6 rounded-lg shadow-md mb-8'>
            <h2 className='text-xl font-semibold mb-4'>Crawl Status</h2>
            {/* <div className='mb-4'>
              <p className='text-sm text-gray-500'>Job ID: {activeJobId}</p>
              <p className='text-sm text-gray-500'>
                Status: {jobStatus.status}
              </p>
            </div> */}

            <div className='mb-2'>
              <div className='flex justify-between mb-1'>
                <span className='text-sm font-medium text-gray-700'>
                  Progress
                </span>
                {/* <span className='text-sm font-medium text-gray-700'>
                  {jobStatus.pages_crawled} / {jobStatus.total_pages || '?'}{' '}
                  pages
                </span> */}
              </div>
              <div className='w-full bg-gray-200 rounded-full h-2.5'>
                <div
                  className='bg-blue-600 h-2.5 rounded-full'
                  style={{
                    width: jobStatus.total_pages
                      ? `${
                          (jobStatus.pages_crawled / jobStatus.total_pages) *
                          100
                        }%`
                      : '0%',
                  }}
                ></div>
              </div>
            </div>

            <p className='text-sm text-gray-500'>
              Test cases generated: {jobStatus.test_cases_generated}
            </p>
          </div>
        )}

        {results && (
          <div className='bg-white p-6 rounded-lg shadow-md'>
            <h2 className='text-xl font-semibold mb-4'>Crawl Results</h2>

            <div className='grid grid-cols-1 md:grid-cols-3 gap-6'>
              <div className='md:col-span-1 border-r pr-4'>
                <h3 className='font-medium text-gray-700 mb-3'>
                  Pages ({Object.keys(results).length})
                </h3>
                <div className='space-y-2 max-h-96 overflow-y-auto pr-2'>
                  {Object.keys(results).map((pageUrl) => (
                    <button
                      key={pageUrl}
                      onClick={() => setSelectedPage(pageUrl)}
                      className={`text-left w-full p-2 rounded text-sm ${
                        selectedPage === pageUrl
                          ? 'bg-blue-100 text-blue-800'
                          : 'hover:bg-gray-100'
                      }`}
                    >
                      <div className='truncate font-medium'>
                        {results[pageUrl].title || pageUrl}
                      </div>
                      <div className='truncate text-xs text-gray-500'>
                        {pageUrl}
                      </div>
                    </button>
                  ))}
                </div>
              </div>

              <div className='md:col-span-2'>
                {selectedPage && results[selectedPage] ? (
                  <>
                    <h3 className='font-medium text-gray-700 mb-3'>
                      Test Cases for {results[selectedPage].title}
                    </h3>
                    <div className='space-y-4 max-h-96 overflow-y-auto pr-2'>
                      {results[selectedPage].test_cases.length > 0 ? (
                        results[selectedPage].test_cases.map((testCase) => (
                          <div
                            key={testCase.id}
                            className='border p-3 rounded-md'
                          >
                            <div className='flex justify-between'>
                              <span className='font-medium'>
                                {testCase.description}
                              </span>
                              <span className='text-xs px-2 py-1 rounded bg-gray-100'>
                                {testCase.test_type}
                              </span>
                            </div>
                            <div className='mt-2 text-sm'>
                              <p>
                                <span className='text-gray-500'>
                                  Element Type:
                                </span>{' '}
                                {testCase.element_type}
                              </p>
                              <p>
                                <span className='text-gray-500'>Selector:</span>{' '}
                                <code className='bg-gray-100 px-1 py-0.5 rounded text-xs'>
                                  {testCase.xpath}
                                </code>
                              </p>
                            </div>
                          </div>
                        ))
                      ) : (
                        <p className='text-gray-500 italic'>
                          No test cases generated for this page
                        </p>
                      )}
                    </div>
                  </>
                ) : (
                  <p className='text-gray-500 italic'>
                    Select a page to view test cases
                  </p>
                )}
              </div>
            </div>
          </div>
        )}
      </main>
    </div>
  );
}
