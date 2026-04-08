(() => {
  // Add styling for the PubMed link if it hasn't already been added.
  if (!document.getElementById('pubmed-link-style')) {
    const style = document.createElement('style');
    style.id = 'pubmed-link-style';
    style.innerHTML = `
      .pubmed-link {
        text-decoration: underline;
        color: inherit;
        cursor: pointer;
      }
      .pubmed-link:hover {
        color: blue;
      }
    `;
    document.head.appendChild(style);
  }

  // Cache the modal element and define the text scale factor.
  const paperModal = document.querySelector('.paper-overlay');
  const TEXT_SCALE_FACTOR = 45; // Adjust as needed for best appearance

  // Define a simple list of stop words.
  const stopWords = ['the', 'and', 'of', 'a', 'an', 'in', 'on', 'for', 'to'];

  /**
   * Splits a title into keywords by filtering out common stop words and very short words.
   * @param {string} title - The title string to filter.
   * @returns {string[]} Array of keywords.
   */
  const filterKeywords = (title) => {
    return title
      .split(/\s+/)
      .filter(word => word.length > 2 && !stopWords.includes(word.toLowerCase()));
  };

  /**
   * Adjusts the font size based on the viewport dimensions.
   * @returns {number} The font size in pixels.
   */
  const rescaleText = () => {
    const height = window.innerHeight,
          width = window.innerWidth;
    return Math.min(width / TEXT_SCALE_FACTOR, height / TEXT_SCALE_FACTOR);
  };

  /**
   * Closes the modal by hiding it and resetting its content.
   */
  const closeModal = () => {
    paperModal.style.display = 'none';
    paperModal.innerHTML = '';
  };

  /**
   * Highlights the given keywords inside a text by wrapping them in a red-colored span.
   * @param {string} text - The original text.
   * @param {string[]} keywords - Array of keywords to highlight.
   * @returns {string} The text with keywords highlighted.
   */
  const highlightKeywords = (text, keywords) => {
    let highlightedText = text;
    keywords.forEach(word => {
      // Escape any regex-special characters.
      const escapedWord = word.replace(/[-\/\\^$*+?.()|[\]{}]/g, '\\$&');
      // Create a regex to match whole words (case-insensitive).
      const regex = new RegExp(`\\b${escapedWord}\\b`, 'gi');
      highlightedText = highlightedText.replace(regex, `<span style="color: red;">$&</span>`);
    });
    return highlightedText;
  };

  /**
   * Removes the leading bracketed label (if present) and any non-alphanumeric
   * characters at the edges. Also ensures the snippet ends with a period.
   *
   * @param {string} rawText - The raw text to be cleaned.
   * @returns {string} - The cleaned text.
   */
  const cleanSnippet = (rawText) => {
    let cleaned = rawText;

    // Remove leading/trailing non-alphanumeric characters.
    cleaned = cleaned.replace(/^[^a-zA-Z0-9]+|[^a-zA-Z0-9]+$/g, '');

    // Remove bracketed labels like "INTRO':", "RESULTS':", etc.
    cleaned = cleaned.replace(
      /^(?:(?:INTRO|RESULTS|DISCUSS|ABSTRACT)':\s*(?:(?:(?:\d+\.\s*)?')|(?:'(?:\d+\.\s*)?)|(?:\d+\.\s*)|)(Introduction|Background|Results|Discussion|Abstract)|(?:TITLEABSTRACT)':\s*')/i,
      ''
    );
    // Trim spaces.
    cleaned = cleaned.trim();

    // Ensure a final period.
    if (cleaned && !cleaned.endsWith('.')) {
      cleaned += '.';
    }

    return cleaned;
  };

  /**
   * Fetches the snippet text from the backend and paper details (title and authors)
   * from the PubMed EFetch API. Then, it displays the content in the modal.
   *
   * If the parameters for source, typa, and target are undefined (or not provided),
   * they are filtered out so that nothing is shown in the title.
   *
   * @param {string} p_source - The PubMed ID (or combined string such as "26771740_results1").
   * @param {string} source - (Optional) Part of the title.
   * @param {string} typa - (Optional) Part of the title.
   * @param {string} target - (Optional) Part of the title.
   */
  const addModalContent = (p_source, source, typa, target, section) => {
    // Show a loading message.
    paperModal.innerHTML = `
      <div class="modal-content" style="font-size: ${rescaleText()}px;">
        <h5>Fetching content...</h5>
      </div>
    `;
    paperModal.style.display = "block";
    paperModal.style.zIndex = "9999";

    // Fetch snippet from your backend.
    const snippetPromise = fetch('/process-text-withoutapi', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({ pmid: p_source, section: section || '' })
    })
    .then(response => {
      if (!response.ok) {
        throw new Error('Snippet API call unsuccessful.');
      }
      return response.json();
    });

    // Fetch paper details from PubMed's EFetch API.
    const pubmedPromise = fetch(`https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi?db=pubmed&id=${p_source}&retmode=xml`)
    .then(response => {
      if (!response.ok) {
        throw new Error('PubMed EFetch API call unsuccessful.');
      }
      return response.text();
    })
    .then(xmlString => {
      const parser = new DOMParser();
      const xmlDoc = parser.parseFromString(xmlString, 'text/xml');
      const articleTitleElem = xmlDoc.querySelector('ArticleTitle');
      const pubmedTitle = articleTitleElem ? articleTitleElem.textContent : 'Title not available.';
      const authorsNodes = xmlDoc.querySelectorAll('Author');
      let authorsArray = [];
      authorsNodes.forEach(author => {
        const collectiveNameElem = author.querySelector('CollectiveName');
        if (collectiveNameElem) {
          authorsArray.push(collectiveNameElem.textContent);
        } else {
          const lastNameElem = author.querySelector('LastName');
          const foreNameElem = author.querySelector('ForeName');
          if (lastNameElem && foreNameElem) {
            authorsArray.push(`${foreNameElem.textContent} ${lastNameElem.textContent}`);
          }
        }
      });
      const pubmedAuthors = authorsArray.length > 0 ? authorsArray.join(', ') : 'Authors not available.';
      return { pubmedTitle, pubmedAuthors };
    });

    // Wait for both fetches to complete.
    Promise.all([snippetPromise, pubmedPromise])
      .then(([snippetData, pubmedDetails]) => {
        let text_input = snippetData.text_input || 'No content returned.';
        text_input = cleanSnippet(text_input);

        // Build the title from the provided parts, filtering out undefined values.
        const titleParts = [source, typa, target].filter(part => part && part !== "undefined");
        const titleString = titleParts.length > 0 ? titleParts.join(' ') : `Publication ${p_source}`;

        // Extract keywords from the title.
        const keywords = filterKeywords(titleString);
        // Highlight keywords in the processed text.
        const highlightedText = highlightKeywords(text_input, keywords);

        // Build the modal's HTML content.
        const contents = `
          <div class="modal-content" style="font-size: ${rescaleText()}px;">
              ${titleString ? `<h4>${titleString}</h4><br>` : ''}
              <h5><strong>PubMed Title:</strong> ${pubmedDetails.pubmedTitle}</h5>
              <p><strong>Authors:</strong> ${pubmedDetails.pubmedAuthors}</p>
              <br>
              <p>
                <a href="https://pubmed.ncbi.nlm.nih.gov/${p_source}" target="_blank" class="pubmed-link">
                  Click here
                </a> to view publication.
              </p>              
              <br>
              <p><strong>Respective text from publication:</strong> ${highlightedText}</p>
          </div>
        `;
        paperModal.innerHTML = contents;
      })
      .catch(error => {
        console.error(`Error while fetching data / rendering modal: ${error.message}`);
        paperModal.innerHTML = `
          <div class="modal-content" style="font-size: ${rescaleText()}px;">
              <h5>Error loading content.</h5>
          </div>
        `;
      });
  };

  // Attach event listeners to elements with the class "pubmed-link" (if any exist)
  const pubmedLinks = document.querySelectorAll('span.pubmed-link');
  pubmedLinks.forEach(link => {
    const p_source = link.getAttribute('data-p_source');
    const source   = link.getAttribute('data-source');
    const typa     = link.getAttribute('data-typa');
    const target   = link.getAttribute('data-target');
    // Attach the event listener.
    link.addEventListener('click', () => addModalContent(p_source, source, typa, target));
  });

  // Close the modal when the user clicks outside the popup content.
  paperModal.addEventListener('click', (event) => {
    if (event.target === paperModal) {
      closeModal();
    }
  });

  // Expose addModalContent globally in case it is referenced elsewhere.
  window.addModalContent = addModalContent;
})();