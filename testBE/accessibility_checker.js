const puppeteer = require('puppeteer');
const { AxePuppeteer } = require('@axe-core/puppeteer');

const url = process.argv[2];

if (!url) {
  console.error(JSON.stringify({ error: 'URL argument is required.' }));
  process.exit(1);
}

(async () => {
  let browser = null;
  try {
    browser = await puppeteer.launch({
      headless: true,
      args: [
        '--no-sandbox',
        '--disable-setuid-sandbox',
        '--disable-dev-shm-usage',
      ],
      timeout: 30000,
    });
    const page = await browser.newPage();

    await page.setViewport({ width: 1280, height: 800 });

    // *** CHANGE HERE: Try 'load' or 'networkidle2' ***
    await page.goto(url, {
      // waitUntil: 'load', // Option A (Recommended first try)
      waitUntil: 'networkidle2', // Option B (Alternative if 'load' fails/timeouts)
      timeout: 60000, // Increase timeout slightly as these waits can take longer
    });
    // ***********************************************

    // Optional: Add a small explicit delay (try if waitUntil change alone isn't enough)
    // await page.waitForTimeout(1500); // Wait 1.5 seconds

    const results = await new AxePuppeteer(page)
      .options({
        /* Axe options if needed */
      })
      .analyze();

    console.log(JSON.stringify(results, null, 2));
  } catch (error) {
    const errorType = error.constructor ? error.constructor.name : 'Error';
    console.error(
      JSON.stringify({
        error: `Accessibility check failed for ${url}: [${errorType}] ${error.message}`,
        stack: error.stack,
      })
    );
    process.exitCode = 1;
  } finally {
    if (browser) {
      await browser.close();
    }
  }
})();
