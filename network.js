
  // Suppress non-critical Cytoscape warnings (wheel sensitivity, overlapping endpoints)
  const _origWarn = console.warn;
  console.warn = function(...args) {
    const msg = args[0];
    if (typeof msg === 'string' && (msg.includes('wheel sensitivity') || msg.includes('invalid endpoints'))) return;
    _origWarn.apply(console, args);
  };

  // ----------------------------
  // 1) PRE-EXISTING CODE
  // ----------------------------

  /**
   * Convert an ALL-CAPS category string to Title Case for display.
   * e.g. "GENE / PROTEIN" → "Gene / Protein"
   *      "GENOMIC / TRANSCRIPTOMIC / PROTEOMIC / EPIGENOMIC FEATURE" → "Genomic / Transcriptomic / Proteomic / Epigenomic Feature"
   */
  function titleCaseCategory(str) {
    if (!str) return str;
    return str.toLowerCase().replace(/(?:^|\s|\/\s*)\S/g, c => c.toUpperCase());
  }

  /**
   * Global constants and data preparation
   */
  let currentSpacing = 80;
  let baselinePositions = {};  // nodeId -> {x, y} — saved after each layout run
  let NODES_TO_RENDER = prepareNodes();
  let EDGES_TO_RENDER = prepareEdges();
  var queryTerm = queryTerms.split(',').map(term => {
    // Strip bracket suffix (e.g., "CESA GENES [Gene / Protein]" -> "CESA GENES")
    let t = term.trim().toUpperCase();
    const bi = t.lastIndexOf(' [');
    if (bi > 0) t = t.substring(0, bi).trim();
    return t;
  });

  /**
   * Utility functions to prepare nodes and edges
   */
  function prepareNodes() {
    return [_INSERT_NODES_HERE_].map(node => ({
      ...node,
      data: {
        ...node.data,
        originalId: node.data.id, // Store original case
        id: node.data.id.toUpperCase(), // Normalize ID to uppercase (name only, no type bracket)
        type: node.data.type,
      },
    }));
  }

  function prepareEdges() {
    return [_INSERT_EDGES_HERE_].map(e => ({
      ...e,
      data: {
        ...e.data,
        source: e.data.source.toUpperCase(),
        originalsource: e.data.source,
        sourcetype: e.data.sourcetype,
        target: e.data.target.toUpperCase(),
        originaltarget: e.data.target,
        targettype: e.data.targettype,
        interaction: e.data.interaction,
        p_source: e.data.p_source,
        pmid: e.data.pmid,
        species: e.data.species,
        basis: e.data.basis,
        source_extracted_definition: e.data.source_extracted_definition,
        source_generated_definition: e.data.source_generated_definition,
        target_extracted_definition: e.data.target_extracted_definition,
        target_generated_definition: e.data.target_generated_definition,
      },
    }));
  }

  /**
   * Merge query nodes that share the same base entity name.
   * E.g., OBESITY [METABOLIC DISORDER], OBESITY [METABOLIC DISEASE] → single OBESITY node.
   */
  (function mergeQueryNodes() {
    // Group query terms by base name (text before the bracket)
    const queryGroups = {};
    queryTerm.forEach(term => {
      const bracketIdx = term.lastIndexOf(' [');
      if (bracketIdx > 0) {
        const baseName = term.substring(0, bracketIdx).trim();
        if (!queryGroups[baseName]) queryGroups[baseName] = [];
        if (!queryGroups[baseName].includes(term)) queryGroups[baseName].push(term);
      }
    });

    // Build merge map: for groups with >1 entry, map all variants to a single canonical ID
    const mergeMap = {}; // oldNodeId → canonicalNodeId
    const updatedQueryTerms = [];

    for (const [, terms] of Object.entries(queryGroups)) {
      if (terms.length <= 1) {
        updatedQueryTerms.push(...terms);
        continue;
      }

      // Canonical = first term; all others redirect to it
      const canonicalId = terms[0];
      terms.slice(1).forEach(term => { mergeMap[term] = canonicalId; });
      updatedQueryTerms.push(canonicalId);

      // Update canonical node: combine types from all variants
      const allTypes = terms.map(t => {
        const bi = t.lastIndexOf(' [');
        return t.substring(bi + 2, t.length - 1);
      });
      const canonicalNode = NODES_TO_RENDER.find(n => n.data.id === canonicalId);
      if (canonicalNode) {
        canonicalNode.data.mergedTypes = allTypes; // store for tooltip
      }
    }

    if (Object.keys(mergeMap).length === 0) return; // nothing to merge

    console.log('Merging central nodes:', mergeMap);

    // Redirect edges from merged nodes to canonical
    EDGES_TO_RENDER.forEach(edge => {
      if (mergeMap[edge.data.source]) {
        edge.data.source = mergeMap[edge.data.source];
      }
      if (mergeMap[edge.data.target]) {
        edge.data.target = mergeMap[edge.data.target];
      }
    });

    // Remove self-loops created by merging
    EDGES_TO_RENDER = EDGES_TO_RENDER.filter(e => e.data.source !== e.data.target);

    // Deduplicate edges (same source → target → category; pmids already merged server-side)
    const seen = new Set();
    EDGES_TO_RENDER = EDGES_TO_RENDER.filter(e => {
      const key = `${e.data.source}|${e.data.target}|${e.data.category}`;
      if (seen.has(key)) return false;
      seen.add(key);
      return true;
    });

    // Re-number edge IDs after deduplication
    EDGES_TO_RENDER.forEach((e, i) => { e.data.id = 'edge' + i; });

    // Remove merged (non-canonical) nodes
    const mergedIds = new Set(Object.keys(mergeMap));
    NODES_TO_RENDER = NODES_TO_RENDER.filter(node => !mergedIds.has(node.data.id));

    // Update queryTerm
    queryTerm = updatedQueryTerms;
  })();

  // After preparing nodes and before rendering the graph:
  const validNodeIds = new Set(NODES_TO_RENDER.map(node => node.data.id));

  // Filter edges: keep only edges where both source and target exist in validNodeIds
  const filteredEdges = EDGES_TO_RENDER.filter(edge =>
    validNodeIds.has(edge.data.source) && validNodeIds.has(edge.data.target)
  );

  // Filter nodes: remove orphan nodes
  const edgeNodeIds = new Set();
  filteredEdges.forEach(edge => {
    edgeNodeIds.add(edge.data.source);
    edgeNodeIds.add(edge.data.target);
  });

  const filteredNodes = NODES_TO_RENDER.filter(node =>
    edgeNodeIds.has(node.data.id) || queryTerm.includes(node.data.id)
  );

  /**
   * Categorization map for node types
   */
  // Node categories are now provided directly from the backend CSV (Connectome_entities.csv)
  // Each node already has a 'category' field in its data.

  // ── Badge helper ──
  function categoryBadge(raw) {
    const label = titleCaseCategory(raw) || 'N/A';
    return `<span class="category-badge">${label}</span>`;
  }

  /**
   * Initialize Cytoscape
   */
  let cy = cytoscape({
    container: document.getElementById('cy'),
    autoungrabify: false,      // allow drag-to-move nodes
    zoomingEnabled: true,
    userPanningEnabled: true,
    wheelSensitivity: 1,
    minZoom: 0.05,
    maxZoom: 3,
    textureOnViewport: false,
    hideEdgesOnViewport: false,
    hideLabelsOnViewport: false,
    elements: [...filteredNodes, ...filteredEdges],
    motionBlur: false,
    pixelRatio: 'auto',
    style: generateStyles(),
    layout: { name: 'preset' },
  });

  /**
   * Generates node and edge styles for Cytoscape
   */
  function generateStyles() {
    const nodeStyles = {
      shapes: {
        // Exact category strings from the data extraction prompt (uppercased)
        'GENE / PROTEIN':                                                    'ellipse',
        'GENOMIC / TRANSCRIPTOMIC / PROTEOMIC / EPIGENOMIC FEATURE':         'round-rectangle',
        'PHENOTYPE / TRAIT / DISEASE':                                       'rectangle',
        'COMPLEX / STRUCTURE / COMPARTMENT / CELL / ORGAN / ORGANISM':       'hexagon',
        'TAXONOMIC / EVOLUTIONARY / PHYLOGENETIC GROUP':                     'heptagon',
        'CHEMICAL / METABOLITE / COFACTOR / LIGAND':                         'diamond',
        'TREATMENT / PERTURBATION / STRESS / MUTANT':                        'pentagon',
        'METHOD / ASSAY / EXPERIMENTAL SETUP / PARAMETER / SAMPLE':          'triangle',
        'BIOLOGICAL PROCESS / PATHWAY / FUNCTION':                           'ellipse',
        'REGULATORY / SIGNALING MECHANISM':                                  'ellipse',
        'COMPUTATIONAL / MODEL / ALGORITHM / DATA / METRIC':                 'triangle',
        'ENVIRONMENTAL / ECOLOGICAL / SOIL / CLIMATE CONTEXT':               'concave-hexagon',
        'CLINICAL / EPIDEMIOLOGICAL / POPULATION':                           'vee',
        'EQUIPMENT / DEVICE / MATERIAL / INSTRUMENT':                        'tag',
        'SOCIAL / ECONOMIC / POLICY / MANAGEMENT':                           'star',
        'KNOWLEDGE / CONCEPT / HYPOTHESIS / THEORETICAL CONSTRUCT':          'star',
        'PROPERTY / MEASUREMENT / CHARACTERIZATION':                         'round-rectangle',
        'OTHER':                                                             'star',
        'OTHERS':                                                            'star',
      },
      colors: {
        'GENE / PROTEIN':                                                    '#89CFF0',
        'GENOMIC / TRANSCRIPTOMIC / PROTEOMIC / EPIGENOMIC FEATURE':         '#AFEEEE',
        'PHENOTYPE / TRAIT / DISEASE':                                       '#90EE90',
        'COMPLEX / STRUCTURE / COMPARTMENT / CELL / ORGAN / ORGANISM':       '#FFB6C1',
        'TAXONOMIC / EVOLUTIONARY / PHYLOGENETIC GROUP':                     '#F0E68C',
        'CHEMICAL / METABOLITE / COFACTOR / LIGAND':                         '#FFD700',
        'TREATMENT / PERTURBATION / STRESS / MUTANT':                        '#E0FFFF',
        'METHOD / ASSAY / EXPERIMENTAL SETUP / PARAMETER / SAMPLE':          '#D2B48C',
        'BIOLOGICAL PROCESS / PATHWAY / FUNCTION':                           '#98FB98',
        'REGULATORY / SIGNALING MECHANISM':                                  '#98FB98',
        'COMPUTATIONAL / MODEL / ALGORITHM / DATA / METRIC':                 '#D2B48C',
        'ENVIRONMENTAL / ECOLOGICAL / SOIL / CLIMATE CONTEXT':               '#87CEEB',
        'CLINICAL / EPIDEMIOLOGICAL / POPULATION':                           '#FF6B6B',
        'EQUIPMENT / DEVICE / MATERIAL / INSTRUMENT':                        '#DEB887',
        'SOCIAL / ECONOMIC / POLICY / MANAGEMENT':                           '#C8A2C8',
        'KNOWLEDGE / CONCEPT / HYPOTHESIS / THEORETICAL CONSTRUCT':          '#D3D3D3',
        'PROPERTY / MEASUREMENT / CHARACTERIZATION':                         '#E8E8E8',
        'OTHER':                                                             '#FFA07A',
        'OTHERS':                                                            '#FFA07A',
      },
      defaultShape: 'star',
      defaultColor: '#FFA07A',
    };

    // Lookup helper: exact match only
    function resolveNodeStyle(category, styleMap, fallback) {
      if (!category) return fallback;
      return styleMap[category.toUpperCase()] || fallback;
    }

    // Edge styles keyed by exact relationship_label values from the database
    const edgeStyles = {
      colors: {
        'Activation / Induction / Causation / Result': '#32CD32',
        'Causation / Activation / Induction / Result': '#32CD32',
        'Causation / Result': '#32CD32',
        'Repression / Inhibition / Negative Regulation': '#DC143C',
        'Regulation / Control': '#4682B4',
        'Expression / Detection / Identification': '#FF8C00',
        'Association / Interaction / Binding': '#8A2BE2',
        'Localization / Containment / Composition': '#3CB371',
        'Composition / Containment / Localization': '#3CB371',
        'Composition / Containment': '#3CB371',
        'Composition / Containment / Composition': '#3CB371',
        'Requirement / Activity / Function / Participation': '#B22222',
        'Encodes / Contains': '#9370DB',
        'Lacks / Dissimilar': '#808080',
        'Synthesis / Formation': '#DAA520',
        'Modification / Changes / Alters': '#FF6347',
        'Comparison / Evaluation / Benchmarking': '#778899',
        'Definition / Classification / Naming': '#6495ED',
        'Classification / Naming': '#6495ED',
        'Property / Characterization': '#BC8F8F',
        'Property / Measurement / Characterization': '#BC8F8F',
        'Hypothesis / Assumption / Proposal': '#DEB887',
        'Temporal / Sequential Relationship': '#5F9EA0',
        'Is / Similarity / Equivalence / Analogy': '#7B68EE',
        'Limitation / Innovation / Improvement / Advancement': '#66CDAA',
        'No Effect / Null Relationship': '#D3D3D3',
        'Biological Process / Pathway / Function / Regulatory / Signaling Mechanism': '#98FB98',
        'Phenotype / Trait / Disease': '#90EE90',
        'Knowledge / Concept / Hypothesis / Theoretical Construct': '#DEB887',
        'Treatment / Perturbation / Stress / Mutant': '#20B2AA',
      },
      arrows: {
        'Activation / Induction / Causation / Result': 'triangle',
        'Causation / Activation / Induction / Result': 'triangle',
        'Causation / Result': 'triangle',
        'Repression / Inhibition / Negative Regulation': 'tee',
        'Regulation / Control': 'tee',
        'Expression / Detection / Identification': 'circle',
        'Association / Interaction / Binding': 'circle',
        'Localization / Containment / Composition': 'circle',
        'Composition / Containment / Localization': 'circle',
        'Composition / Containment': 'circle',
        'Requirement / Activity / Function / Participation': 'diamond',
        'Encodes / Contains': 'circle',
        'Lacks / Dissimilar': 'tee',
        'Synthesis / Formation': 'triangle',
        'Modification / Changes / Alters': 'triangle',
        'Comparison / Evaluation / Benchmarking': 'circle',
        'Definition / Classification / Naming': 'circle',
        'Property / Characterization': 'circle',
        'Hypothesis / Assumption / Proposal': 'diamond',
        'Temporal / Sequential Relationship': 'triangle',
        'Is / Similarity / Equivalence / Analogy': 'circle',
        'Limitation / Innovation / Improvement / Advancement': 'triangle',
        'No Effect / Null Relationship': 'tee',
      },
      defaultColor: '#C0C0C0',
      defaultArrow: 'triangle',
    };

    return [
      // Node style
      {
        selector: 'node',
        style: {
          label: (ele) => ele.data('originalId'),
          width: 55,
          height: 55,
          color: '#1a1a2e',
          'font-size': '11px',
          'min-zoomed-font-size': 6,
          'text-halign': 'center',
          'text-valign': 'center',
          'text-wrap': 'wrap',
          'text-max-width': 120,
          'border-width': 1.5,
          'border-color': '#ffffff',
          'border-opacity': 0.8,
          shape: (ele) => resolveNodeStyle(ele.data('category'), nodeStyles.shapes, nodeStyles.defaultShape),
          'background-color': (ele) => resolveNodeStyle(ele.data('category'), nodeStyles.colors, nodeStyles.defaultColor),
          'background-opacity': 0.9,
        },
      },
      // Edge style
      {
        selector: 'edge',
        style: {
          width: 1.5,
          'line-color': (ele) => edgeStyles.colors[ele.data('category')] || edgeStyles.defaultColor,
          'line-opacity': 0.6,
          'target-arrow-color': (ele) => edgeStyles.colors[ele.data('category')] || edgeStyles.defaultColor,
          'target-arrow-shape': (ele) => edgeStyles.arrows[ele.data('category')] || edgeStyles.defaultArrow,
          'arrow-scale': 0.8,
          'curve-style': 'bezier',
          'min-zoomed-font-size': 1,
          label: (ele) => ele.data('interaction') || '',
          'font-size': '8px',
          'color': '#666',
          'text-wrap': 'wrap',
          'text-max-width': 80,
          'text-rotation': 'autorotate',
          'text-margin-y': -8,
          'text-background-color': '#ffffff',
          'text-background-opacity': 0.6,
          'text-background-padding': '1px',
        },
      },
      // Clicked/selected node — subtle highlight (not red)
      {
        selector: 'node:selected',
        style: {
          'border-width': 2.5,
          'border-color': '#3498db',
          'background-opacity': 1,
        },
      },
    ];
  }
  function isCentralNode(node) {
    // Suppose central nodes are those matching any of the queryTerms
    // in uppercase. If you prefer a different logic, adjust accordingly.
    return queryTerm.some((term) => node.id() === term);
  }
  /**
   * Function to style the central nodes
   */
  function styleCentralNodes(queryTerm) {
    cy.startBatch();
    cy.nodes().forEach((node) => {
      if (queryTerm.some((term) => node.id() === term)) {
        node.style({
          width: 70,
          height: 70,
          'background-opacity': 1,
          'border-width': 2.5,
          'border-color': '#c0392b',
          color: '#c0392b',
          'font-size': '12px',
          'font-weight': 'bold',
          'text-halign': 'center',
          'text-valign': 'center',
          'text-wrap': 'wrap',
          'text-max-width': 100,
          'z-index': 9999,
        });
      }
    });
    cy.endBatch();
  }

  /**
   * Event Listeners
   */
  function initializeEventListeners() {
    // Node click listener
    cy.on('click', 'node', handleNodeClick);

    // Edge click listener
    cy.on('click', 'edge', handleEdgeClick);

    // Background click listener to reset or detect double-click
    let lastClickTime = 0;
    const doubleClickDelay = 300; // ms

    cy.on('click', (evt) => {
      if (evt.target === cy) {
        // Close all panels on background click
        closeAllPanels();
        const vsp = document.getElementById('viewSettingsPanel');
        if (vsp) vsp.style.display = 'none';

        const currentTime = new Date().getTime();
        const timeDiff = currentTime - lastClickTime;
        if (timeDiff < doubleClickDelay) {
          // Double-click detected
          handleGraphDoubleClick();
        } else {
          // Single click => reset the view after doubleClickDelay
          setTimeout(() => {
            resetNetworkView();
          }, doubleClickDelay);
        }
        lastClickTime = currentTime;
      }
    });
  }

  /**
   * Node/Edge click handlers and related logic
   */
  let currentNode = null; // Stores the currently clicked node
  let removedEles = cy.collection(); // Stores removed elements for restoration

  function handleNodeClick(evt) {
    currentNode = evt.target;
    const neighborhood = currentNode.neighborhood().add(currentNode);

    highlightNeighborhood(neighborhood);
    showTooltipForNode(currentNode);

    updateNumNodes();
    updatePaperCount();
    updateNodeSummaries();
  }

  function handleEdgeClick(evt) {
    const edge = evt.target;
    highlightEdgeNeighborhood(edge);
    showTooltipForEdge(edge);

    updateNumNodes();
    updatePaperCount();
    updateNodeSummaries();
  }

  /**
   * Resets the network view to full opacity
   */
  function resetNetworkView() {
    cy.startBatch();
    cy.nodes().style('opacity', '1');
    cy.edges().style('opacity', '1');
    hideTooltip();
    toggleMinimizeHide();
    updateNodeSummaries();
    updateNumNodes();
    updatePaperCount();
    cy.endBatch();
  }

  /**
   * Removes the currently selected node from the network
   */
  function removeNode() {
    removedEles = removedEles.union(currentNode.remove());
    updateNumNodes();
    updatePaperCount();
    updateNodeSummaries();
  }

  /**
   * Double-click on background to restore all nodes
   */
  function handleGraphDoubleClick() {
    console.log('Restoring removed nodes and resetting view');
    if (removedEles && removedEles.length > 0) {
      removedEles.restore();
    } else {
      console.log('No elements to restore');
    }
    cy.nodes().style('opacity', '1');
    hideTooltip();
    cy.fit();
    currentNode = null;
    updateNodeSummaries();
    updateNumNodes();
    updatePaperCount();
  }

  /**
   * Highlights a node's neighborhood
   */
  function highlightNeighborhood(neighborhood) {
    const nonNeighbors = cy.nodes().difference(neighborhood);

    cy.startBatch();
    neighborhood.style('opacity', '1');
    nonNeighbors.style('opacity', '0.5');
    cy.edges()
      .filter((edge) => nonNeighbors.contains(edge.source()) || nonNeighbors.contains(edge.target()))
      .style('opacity', '0.5');
    cy.endBatch();
  }

  /**
   * Highlights an edge's source and target nodes
   */
  function highlightEdgeNeighborhood(edge) {
    cy.startBatch();
    cy.nodes().style('opacity', '0.5');
    cy.edges().style('opacity', '0.5');

    edge.source().style('opacity', '1');
    edge.target().style('opacity', '1');
    edge.style('opacity', '1');

    cy.endBatch();
  }

  /**
   * Closes all open panels (tooltip, filters, validation results, definitions)
   * Call this before opening any new panel to ensure only one is visible at a time.
   */
  function closeAllPanels(except) {
    const panels = {
      'side-tooltip': document.getElementById('side-tooltip'),
      'nodeFilterForm': document.getElementById('nodeFilterForm'),
      'edgeFilterForm': document.getElementById('edgeFilterForm'),
    };
    // Also close validation result container if it exists
    const valContainer = document.getElementById('apiResultContainer');
    if (valContainer) panels['apiResultContainer'] = valContainer;

    for (const [name, el] of Object.entries(panels)) {
      if (el && name !== except) {
        el.style.display = 'none';
      }
    }
  }

  /**
   * Hides the tooltip
   */
  function hideTooltip() {
    document.getElementById('side-tooltip').style.display = 'none';
  }

  /**
   * Displays a tooltip for a clicked node
   */
  function showTooltipForNode(node) {
    closeAllPanels('side-tooltip');
    const ab = document.getElementById('ab');
    const tooltip = document.getElementById('side-tooltip');
    const abTitle = document.getElementById('ab-title');
    const nodeinfo = document.getElementsByClassName('nodeinfo');
    const pmidRow = document.getElementById('pmid-row');
    const nodeId = node.data().originalId;

    // Reveal elements with the "nodeinfo" class
    for (let i = 0; i < nodeinfo.length; i++) {
      nodeinfo[i].style.display = 'block';
    }

    // Hide Source Text row for nodes
    if (pmidRow) pmidRow.style.display = 'none';

    const mergedTypes = node.data().mergedTypes;
    const typeDisplay = mergedTypes
      ? mergedTypes.join(' / ')
      : node.data().type;

    const nodeIdentifier = node.data().identifier || '';
    const nodeCategory = titleCaseCategory(node.data().category || node.data().originalcategory || '');
    abTitle.innerHTML = `
      <div class="node-tp-header">
        <span class="node-tp-name">${nodeId}</span>
        <span style="font-size:0.75em;color:#6b7280;">(${typeDisplay})</span>
        ${nodeCategory ? ` <span class="edge-tp-category-badge">${nodeCategory}</span>` : ''}
      </div>
    `;

    // Node info card
    let nodeInfoHtml = `
      <div class="edge-tp-section-title">Entity Information</div>
      <div class="edge-tp-meta">
        <div class="edge-tp-row"><span class="edge-tp-label">Entity Name</span><span><strong>${nodeId}</strong></span></div>
        <div class="edge-tp-row"><span class="edge-tp-label">Entity Type</span><span>${titleCaseCategory(typeDisplay)}</span></div>
        ${nodeCategory ? `<div class="edge-tp-row"><span class="edge-tp-label">Entity Category</span><span><span class="edge-tp-category-badge">${nodeCategory}</span></span></div>` : ''}
        ${nodeIdentifier ? `<div class="edge-tp-row"><span class="edge-tp-label">Gene Identifier</span><span>${nodeIdentifier}</span></div>` : ''}
      </div>

    `;

    // Connected edges
    let edgeInfo = '';
    const connectedEdges = node.connectedEdges();
    if (connectedEdges.length > 0) {
      edgeInfo += `<div class="edge-tp-section-title" style="margin-top:6px;">Connected Relationships (${connectedEdges.length})</div>`;
    }

    connectedEdges.forEach((edge) => {
      const isSource = edge.data().source === node.data().id;
      const isTarget = edge.data().target === node.data().id;
      if (!isSource && !isTarget) return;

      const otherName = isSource ? edge.data().originaltarget : edge.data().originalsource;
      const otherType = isSource ? edge.data().targettype : edge.data().sourcetype;
      const direction = isSource ? '&rarr;' : '&larr;';
      const interaction = edge.data().interaction;
      const edgeCat = titleCaseCategory(edge.data().category) || '';

      const extractedDef = isSource
        ? (edge.data().source_extracted_definition || '')
        : (edge.data().target_extracted_definition || '');
      const generatedDef = isSource
        ? (edge.data().source_generated_definition || '')
        : (edge.data().target_generated_definition || '');

      edgeInfo += `
        <div class="node-tp-edge">
          <div class="edge-tp-connection" style="font-size:12px;">
            <strong>${nodeId}</strong>
            <span style="color:#DC143C;font-weight:600;">${direction} ${interaction} ${direction}</span>
            <strong>${otherName}</strong> <small style="color:#6b7280;">(${otherType})</small>
          </div>
          ${edgeCat && edgeCat !== 'N/A' && edgeCat !== 'Na'
            ? `<div style="margin:2px 0 4px 0;"><span style="font-size:10px;color:#6b7280;">Relationship Category:</span> <span class="edge-tp-category-badge">${edgeCat}</span></div>`
            : ''}
          ${extractedDef || generatedDef ? `
          <div class="edge-tp-def-group" style="margin-top:4px;">
            <div class="edge-tp-def-title source">Definition of ${nodeId}</div>
            ${extractedDef ? `<div class="edge-tp-def-item"><span class="edge-tp-def-label">From paper:</span> ${extractedDef}</div>` : ''}
            ${generatedDef ? `<div class="edge-tp-def-item"><span class="edge-tp-def-label">AI-generated:</span> ${generatedDef}</div>` : ''}
          </div>` : ''}
        </div>
      `;
    });

    ab.innerHTML = nodeInfoHtml + edgeInfo;
    tooltip.style.display = 'block';

  }

  /**
   * Displays a tooltip for a clicked edge
   */
  function showTooltipForEdge(edge) {
    closeAllPanels('side-tooltip');
    const tooltip = document.getElementById('side-tooltip');
    const ab = document.getElementById('ab');
    const abTitle = document.getElementById('ab-title');
    const pmidElem = document.getElementById('pmid');
    const nodeinfo = document.getElementsByClassName('nodeinfo');
    const edgeinfo2 = document.getElementsByClassName('edgeinfo2');

    // Hide elements with the "nodeinfo" class
    for (let i = 0; i < nodeinfo.length; i++) {
      nodeinfo[i].style.display = 'none';
    }

    // Show elements with the "edgeinfo2" class
    for (let i = 0; i < edgeinfo2.length; i++) {
      edgeinfo2[i].style.display = 'block';
    }

    const srcName = edge.data().originalsource;
    const srcType = edge.data().sourcetype;
    const tgtName = edge.data().originaltarget;
    const tgtType = edge.data().targettype;
    const interactionText = edge.data().interaction;
    const categoryText = titleCaseCategory(edge.data().category) || 'N/A';
    const pmid = edge.data().pmid;
    const section = edge.data().p_source || 'N/A';
    const speciesText = edge.data().species || 'N/A';
    const basisText = edge.data().basis || 'N/A';

    const srcIdent = edge.data().source_identifier || '';
    const tgtIdent = edge.data().target_identifier || '';
    const assocProcess = edge.data().associated_process || '';
    const genProcess = edge.data().generated_process || '';
    const citations = edge.data().relevant_citations || '';
    // Get categories from node data
    const srcNode = cy.getElementById(edge.data().source);
    const tgtNode = cy.getElementById(edge.data().target);
    const srcCat = titleCaseCategory(srcNode?.data()?.category || srcNode?.data()?.originalcategory || '');
    const tgtCat = titleCaseCategory(tgtNode?.data()?.category || tgtNode?.data()?.originalcategory || '');

    abTitle.innerHTML = `
      <div class="edge-tp-header">
        <span class="edge-tp-interaction">Edge Details</span>
      </div>
    `;

    ab.innerHTML = `
      <div class="edge-tp-section-title">Relationship</div>
      <div class="edge-tp-connection">
        <span class="edge-tp-source"><strong>${srcName}</strong> <small style="color:#6b7280;">(${srcType})</small>${srcCat ? ` <span class="edge-tp-category-badge">${srcCat}</span>` : ''}${srcIdent ? ` <small style="color:#6b7280;">ID: ${srcIdent}</small>` : ''}</span>
        <span class="edge-tp-arrow">&xrarr; <span style="color:#DC143C;font-weight:600;">${interactionText}</span> &xrarr;</span>
        <span class="edge-tp-target"><strong>${tgtName}</strong> <small style="color:#6b7280;">(${tgtType})</small>${tgtCat ? ` <span class="edge-tp-category-badge">${tgtCat}</span>` : ''}${tgtIdent ? ` <small style="color:#6b7280;">ID: ${tgtIdent}</small>` : ''}</span>
      </div>
      ${categoryText && categoryText !== 'N/A' && categoryText !== 'Na'
        ? `<div style="margin:4px 0 8px 0;"><span style="font-size:10px;color:#6b7280;">Relationship Category:</span> <span class="edge-tp-category-badge">${categoryText}</span></div>`
        : ''}

      <button id="validateEdge" class="edge-tp-validate-btn">Validate with AI</button>

      <div class="edge-tp-section-title">Details</div>
      <div class="edge-tp-meta">
        ${speciesText !== 'N/A' ? `<div class="edge-tp-row"><span class="edge-tp-label">Species / Organism</span><span>${speciesText}</span></div>` : ''}
        ${basisText !== 'N/A' ? `<div class="edge-tp-row"><span class="edge-tp-label">Evidence Basis</span><span>${basisText}</span></div>` : ''}
      </div>

      ${assocProcess || genProcess || citations ? `
      <div class="edge-tp-section-title">Associated Process / Pathway</div>
      <div class="edge-tp-meta">
        ${assocProcess ? `<div class="edge-tp-row"><span class="edge-tp-label">From Paper (Extracted)</span><span>${assocProcess}</span></div>` : ''}
        ${genProcess ? `<div class="edge-tp-row"><span class="edge-tp-label">AI-Generated</span><span>${genProcess}</span></div>` : ''}
        ${citations ? `<div class="edge-tp-row"><span class="edge-tp-label">Relevant Citations</span><span>${citations}</span></div>` : ''}
      </div>` : ''}

      <div class="edge-tp-section-title">Entity Definitions</div>
      <div class="edge-tp-defs">
        <div class="edge-tp-def-group">
          <div class="edge-tp-def-title source">${srcName} <small style="color:#6b7280;">(${srcType})</small>${srcCat ? ` <span class="edge-tp-category-badge" style="font-size:9px;">${srcCat}</span>` : ''}</div>
          ${edge.data().source_extracted_definition ? `<div class="edge-tp-def-item"><span class="edge-tp-def-label">From paper:</span> ${edge.data().source_extracted_definition}</div>` : ''}
          ${edge.data().source_generated_definition ? `<div class="edge-tp-def-item"><span class="edge-tp-def-label">AI-generated:</span> ${edge.data().source_generated_definition}</div>` : ''}
          ${!edge.data().source_extracted_definition && !edge.data().source_generated_definition ? `<div class="edge-tp-def-item" style="color:#9ca3af;"><em>No definition available</em></div>` : ''}
        </div>
        <div class="edge-tp-def-group">
          <div class="edge-tp-def-title target">${tgtName} <small style="color:#6b7280;">(${tgtType})</small>${tgtCat ? ` <span class="edge-tp-category-badge" style="font-size:9px;">${tgtCat}</span>` : ''}</div>
          ${edge.data().target_extracted_definition ? `<div class="edge-tp-def-item"><span class="edge-tp-def-label">From paper:</span> ${edge.data().target_extracted_definition}</div>` : ''}
          ${edge.data().target_generated_definition ? `<div class="edge-tp-def-item"><span class="edge-tp-def-label">AI-generated:</span> ${edge.data().target_generated_definition}</div>` : ''}
          ${!edge.data().target_extracted_definition && !edge.data().target_generated_definition ? `<div class="edge-tp-def-item" style="color:#9ca3af;"><em>No definition available</em></div>` : ''}
        </div>
      </div>
    `;

    // Show Source Text row and add link
    const pmidRow = document.getElementById('pmid-row');
    if (pmidRow) pmidRow.style.display = 'block';
    const isRealPmid = /^\d+$/.test(pmid);
    const sectionLabel = section !== 'N/A' ? ` | Section: ${section}` : '';
    pmidElem.innerHTML = isRealPmid
      ? `PMID: <a href="https://pubmed.ncbi.nlm.nih.gov/${pmid}" target="_blank" style="color:#3498db;">${pmid}</a>${sectionLabel}`
      : `Source Text${sectionLabel}`;
    pmidElem.onclick = () =>
      openPMIDModal(
        pmid,
        `${srcName} [${srcType}]`,
        interactionText,
        `${tgtName} [${tgtType}]`,
        section !== 'N/A' ? section : ''
      );

    // Add event listener to validate edge button
    document.getElementById('validateEdge').addEventListener('click', () => {
      validateEdgeAPI(
        pmid,
        `${srcName} [${srcType}]`,
        interactionText,
        `${tgtName} [${tgtType}]`,
        section !== 'N/A' ? section : ''
      );
    });

    tooltip.style.display = 'block';
  }

  /**
   * Function to handle API validation and display streamed results
   */
  function validateEdgeAPI(pmid, source, interaction, target, section) {
    console.log("📡 Sending request to /process-text:", { pmid, source, interaction, target, section });

    let resultContainer = document.getElementById('validationResult');
    const cyWrapper = document.getElementById('cy_wrapper');

    // If validationResult is not inside cy_wrapper, move it there
    if (!cyWrapper.contains(resultContainer)) {
      resultContainer.remove(); // Remove old instance
      resultContainer = document.createElement('div');
      resultContainer.id = 'validationResult';
      cyWrapper.appendChild(resultContainer);
    }

    // Style the container
    resultContainer.style.position = 'absolute';
    resultContainer.style.bottom = '0px';
    resultContainer.style.left = '0px';
    resultContainer.style.backgroundColor = 'rgba(255, 255, 255, 0.95)';
    resultContainer.style.color = '#333';
    resultContainer.style.padding = '10px'; // Reduced padding
    resultContainer.style.borderRadius = '8px';
    resultContainer.style.boxShadow = '0px 4px 8px rgba(0, 0, 0, 0.2)';
    resultContainer.style.width = '320px';
    resultContainer.style.height = '100%';
    resultContainer.style.zIndex = '9999';
    resultContainer.style.display = 'block';
    resultContainer.innerHTML = ""; // Clear previous results

    // Create a header with a minimize button
    const header = document.createElement("div");
    header.style.background = '#3498db';
    header.style.color = 'white';
    header.style.padding = '5px'; // Reduced header padding
    header.style.fontWeight = 'bold';
    header.style.display = 'flex';
    header.style.justifyContent = 'space-between';
    header.style.alignItems = 'center';
    header.style.borderTopLeftRadius = '8px';
    header.style.borderTopRightRadius = '8px';
    header.innerHTML = "<span>AI Validation</span><span style='cursor:pointer;' onclick='toggleMinimize()'>➖</span>";
    resultContainer.appendChild(header);

    // Create a content container
    const resultBox = document.createElement('div');
    resultBox.classList.add('summary-container');
    resultBox.style.border = '1px solid #ddd';
    resultBox.style.padding = '8px';
    resultBox.style.margin = '0';
    resultBox.style.backgroundColor = '#f8f9fa';
    resultBox.style.fontFamily = 'Arial, sans-serif';
    resultBox.style.fontSize = '14px';
    resultBox.style.lineHeight = '1.5';
    resultBox.style.height = '95%';
    resultBox.style.maxHeight = '95%';
    resultBox.style.overflowY = 'auto';
    resultContainer.appendChild(resultBox);

    // Show loading indicator
    resultBox.innerHTML = `
      <div style="text-align:center;padding:20px;">
        <div style="display:inline-block;width:24px;height:24px;border:3px solid #e5e7eb;border-top-color:#3498db;border-radius:50%;animation:spin 0.8s linear infinite;"></div>
        <p style="margin-top:10px;color:#6b7280;font-size:13px;">Validating relationship with AI...</p>
        <p style="color:#9ca3af;font-size:11px;">Fetching source text and analyzing with GPT-4o-mini</p>
      </div>
      <style>@keyframes spin{to{transform:rotate(360deg)}}</style>
    `;

    // Create a single paragraph inside the container
    const paragraph = document.createElement("p");
    paragraph.style.margin = '0';
    paragraph.style.color = '#333';

    let accumulatedText = ""; // Store incoming text chunks

    fetch('/process-text', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ pmid, source, interaction, target, section })
    })
    .then(response => {
      if (!response.ok) {
        return response.json().then(errData => {
          throw new Error(errData.error || `Server Error: ${response.statusText}`);
        });
      }
      const reader = response.body.getReader();
      const decoder = new TextDecoder("utf-8");

      let firstChunk = true;
      function readStream() {
        return reader.read().then(({ done, value }) => {
          if (done) {
            console.log("✅ Stream completed");
            return;
          }
          // On first chunk, replace loading indicator with paragraph
          if (firstChunk) {
            resultBox.innerHTML = '';
            resultBox.appendChild(paragraph);
            firstChunk = false;
          }
          // Decode and accumulate the chunk
          const chunk = decoder.decode(value, { stream: true });
          accumulatedText += chunk;

          // Render the text as Markdown
          paragraph.innerHTML = marked.parse(accumulatedText);

          // Continue reading until done
          return readStream();
        });
      }
      return readStream();
    })
    .catch(error => {
      console.error("Error validating edge:", error);
      resultBox.innerHTML = `
        <div style="text-align:center;padding:20px;">
          <div style="font-size:24px;">&#9888;</div>
          <p style="color:#D32F2F;font-weight:600;margin-top:8px;">Validation Failed</p>
          <p style="color:#6b7280;font-size:12px;">${error.message}</p>
        </div>
      `;
    });
  }

  // Minimize/hide functions for the validation result container
  function toggleMinimize() {
    const resultContainer = document.getElementById('validationResult');
    const resultBox = document.querySelector('#validationResult .summary-container');
    
    const minimizedHeight = '55px';
    if (resultBox) {
      if (resultBox.style.display === 'none') {
        // If hidden, show
        resultBox.style.display = 'block';
        resultContainer.style.height = '100%';
      } else {
        // If visible, hide
        resultBox.style.display = 'none';
        resultContainer.style.height = minimizedHeight;
      }
    }
  }
  function toggleHide() {
    const resultContainer = document.getElementById('validationResult');
    if (resultContainer) {
      resultContainer.style.display = 'none';
    }
  }
  function toggleMinimizeHide() {
    const resultContainer = document.getElementById('validationResult');
    if (!resultContainer) return;
    const resultBox = resultContainer.querySelector('.summary-container');
    if (resultBox) {
      resultBox.style.display = 'none';
      resultContainer.style.height = '55px';
    }
  }

  /**
   * Opens a modal to show more details for a given PMID
   */
  function openPMIDModal(pmid, originalSource, interaction, originalTarget, section) {
    addModalContent(pmid, originalSource, interaction, originalTarget, section);
    console.log(`Opening modal for PMID: ${pmid}`);
  }

  /**
   * Node filter form handling
   */
  function openNodeFilterForm() {
    const nodeFilterForm = document.getElementById('nodeFilterForm');
    const isOpen = nodeFilterForm.style.display === 'block';
    closeAllPanels();
    nodeFilterForm.style.display = isOpen ? 'none' : 'block';
  }
  function nodecloseForm() {
    document.getElementById('nodeFilterForm').style.display = 'none';
  }

  /**
   * Edge filter form handling
   */
  function openEdgeFilterForm() {
    const edgeFilterForm = document.getElementById('edgeFilterForm');
    const isOpen = edgeFilterForm.style.display === 'block';
    closeAllPanels();
    edgeFilterForm.style.display = isOpen ? 'none' : 'block';
  }
  function edgecloseForm() {
    document.getElementById('edgeFilterForm').style.display = 'none';
  }

  /**
   * Utility function to determine node category from its data
   */
  function getNodeCategory(_nodeType, node) {
    // Use category from backend if available
    if (node && node.data('category')) {
      return node.data('category');
    }
    return 'OTHER';
  }

  /**
   * Updates the number of visible nodes in the network
   */
  function updateNumNodes() {
    const visibleNodes = cy.nodes().filter(
      (node) => node.visible() && parseFloat(node.style('opacity')) === 1
    ).length;
    document.getElementById('element-len').textContent = `${visibleNodes} nodes`;
  }

  /**
   * Updates the number of papers (PMIDs) related to the visible edges
   */
  function updatePaperCount() {
    const pmids = new Set();
    cy.edges()
      .filter((edge) => edge.visible() && parseFloat(edge.style('opacity')) === 1)
      .forEach((edge) => {
        const pmid = edge.data('pmid');
        if (pmid) pmids.add(pmid);
      });
    document.getElementById('number-papers').textContent = `${pmids.size}`;
  }

  /**
   * Isolates the selected node’s neighborhood
   */
  function isolateNeighborhood() {
    cy.startBatch();
    const neighborhood = currentNode.neighborhood().add(currentNode);
    removedEles = cy.elements().difference(neighborhood).remove();

    updateNumNodes();
    updatePaperCount();
    updateNodeSummaries();

    const layout = neighborhood.layout({
      name: 'cose',
      animate: true,
      animationDuration: 800,
      padding: 30,
      fit: true,
      nodeRepulsion: 600000,
      idealEdgeLength: 80,
      gravity: 50,
      nodeDimensionsIncludeLabels: true,
    });
    layout.run();

    cy.endBatch();
  }

  /**
   * Summaries
   */
  function updateNodeSummaries() {
    const networkSummaryDiv = document.getElementById('networkSummary');
    if (!networkSummaryDiv) {
      // Retry after DOM is ready
      setTimeout(updateNodeSummaries, 500);
      return;
    }

    const nodeSummaries = {};
    const visibleEdges = cy
      .edges()
      .filter((edge) => edge.visible() && parseFloat(edge.style('opacity')) === 1)
      .map((edge) => {
        const srcNode = cy.getElementById(edge.data().source);
        const tgtNode = cy.getElementById(edge.data().target);
        const srcCat = titleCaseCategory(srcNode?.data()?.category || '');
        const tgtCat = titleCaseCategory(tgtNode?.data()?.category || '');
        return {
          source: edge.data().originalsource + ' (' + edge.data().sourcetype + ')' + (srcCat ? ' [' + srcCat + ']' : ''),
          interaction: edge.data().interaction,
          target: edge.data().originaltarget + ' (' + edge.data().targettype + ')' + (tgtCat ? ' [' + tgtCat + ']' : ''),
          pmid: edge.data().pmid,
          section: edge.data().p_source || '',
        };
      });

    visibleEdges.forEach((edge) => {
      const { source, interaction, target, pmid } = edge;
      if (!nodeSummaries[source]) {
        nodeSummaries[source] = {};
      }
      const key = interaction;
      if (!nodeSummaries[source][key]) {
        nodeSummaries[source][key] = [];
      }
      nodeSummaries[source][key].push({ target, pmid, section: edge.section });
    });

    // Sort by number of unique interactions
    const sortedNodes = Object.keys(nodeSummaries)
      .map((source) => {
        const totalInteractions = Object.keys(nodeSummaries[source]).length;
        return {
          source,
          totalInteractions,
          summaries: nodeSummaries[source],
        };
      })
      .sort((a, b) => b.totalInteractions - a.totalInteractions);

    let summaryText = '';
    sortedNodes.forEach((node) => {
      summaryText += `<span style='color: #191970;'>${node.source} </span>`;
      const summaries = node.summaries;
      let firstInteraction = true;

      for (const [interaction, value] of Object.entries(summaries)) {
        const targets = value
          .map(
            ({ target, pmid, section }) => `
              <span style='color: #800000;'>${target}</span>
              (PMID: <a class="tooltippubmed-link tooltippubmed-hyperlink" href="javascript:void(0)"
                data-pmid="${pmid}" data-source="${node.source}" data-interaction="${interaction}"
                data-target="${target}" data-section="${section || ''}">${pmid && section && pmid.endsWith('_' + section) ? pmid : (pmid + (section ? '_' + section : ''))}</a>)
            `
          )
          .join(', ');

        if (!firstInteraction) {
          summaryText += '; ';
        }
        summaryText += `<span style='color: #DC143C;'>${interaction}</span> ${targets}`;
        firstInteraction = false;
      }
      summaryText += '.<br><br>';
    });

    networkSummaryDiv.innerHTML = summaryText;

    // PubMed link event
    document.querySelectorAll('.tooltippubmed-link').forEach((link) => {
      const pmidValue = link.getAttribute('data-pmid');
      const source = link.getAttribute('data-source');
      const interaction = link.getAttribute('data-interaction');
      const target = link.getAttribute('data-target');
      const section = link.getAttribute('data-section');

      link.onclick = () => openPMIDModal(pmidValue, source, interaction, target, section);
    });
  }

  /**
   * Show definitions for the search term
   */
  function showDefinitionsForSearchTerm(queryTerms) {
    const nodeSummary = document.getElementById('nodeSummary');
    const definitionsContainer = document.getElementById('definitionsContainer');
    const itemsPerPage = 5;
    let extractedDefinitions = [];
    let generatedDefinitions = [];
    let found = false;
    const uniqueDefinitions = new Set();
    const edgesArray = cy.edges().toArray();

    for (let i = 0; i < edgesArray.length; i++) {
      const edge = edgesArray[i];
      const pmidValue = edge.data().pmid;
      const sectionValue = edge.data().p_source || '';
      const sourceUpper = edge.data().source;
      const targetUpper = edge.data().target;

      const isSourceMatch = queryTerms.some((term) => sourceUpper.includes(term.toUpperCase()));
      const isTargetMatch = queryTerms.some((term) => targetUpper.includes(term.toUpperCase()));

      if (isSourceMatch || isTargetMatch) {
        found = true;
        const createDefinitionKey = (definition, pmid) => `${definition}-${pmid}`;

        // Source extracted definition
        if (
          isSourceMatch &&
          edge.data().source_extracted_definition &&
          edge.data().source_extracted_definition !== 'nan'
        ) {
          const entitynametype = `${edge.data().originalsource} [${edge.data().sourcetype}]`;
          const definitionKey = createDefinitionKey(edge.data().source_extracted_definition, pmidValue);
          if (!uniqueDefinitions.has(definitionKey)) {
            uniqueDefinitions.add(definitionKey);
            extractedDefinitions.push(`
              <li class="definition-item">
                <span class="definition-entity">${entitynametype}</span>
                <span class="definition-text">${edge.data().source_extracted_definition}</span>
                <span class="definition-pmid">PMID: <a class="tooltippubmed-link tooltippubmed-hyperlink" href="javascript:void(0)"
                  data-pmid="${pmidValue}" data-source="${entitynametype}" data-interaction="${edge.data().interaction}"
                  data-target="${edge.data().originaltarget} [${edge.data().targettype}]" data-section="${sectionValue}">${pmidValue && sectionValue && pmidValue.endsWith('_' + sectionValue) ? pmidValue : (pmidValue + (sectionValue ? '_' + sectionValue : ''))}</a></span>
              </li>
            `);
          }
        }

        // Target extracted definition
        if (
          isTargetMatch &&
          edge.data().target_extracted_definition &&
          edge.data().target_extracted_definition !== 'nan'
        ) {
          const entitynametype = `${edge.data().originaltarget} [${edge.data().targettype}]`;
          const definitionKey = createDefinitionKey(edge.data().target_extracted_definition, pmidValue);
          if (!uniqueDefinitions.has(definitionKey)) {
            uniqueDefinitions.add(definitionKey);
            generatedDefinitions.push(`
              <li class="definition-item">
                <span class="definition-entity">${entitynametype}</span>
                <span class="definition-text">${edge.data().target_extracted_definition}</span>
                <span class="definition-pmid">PMID: <a class="tooltippubmed-link tooltippubmed-hyperlink" href="javascript:void(0)"
                  data-pmid="${pmidValue}" data-source="${edge.data().originalsource} [${edge.data().sourcetype}]"
                  data-interaction="${edge.data().interaction}" data-target="${entitynametype}" data-section="${sectionValue}">${pmidValue && sectionValue && pmidValue.endsWith('_' + sectionValue) ? pmidValue : (pmidValue + (sectionValue ? '_' + sectionValue : ''))}</a></span>
              </li>
            `);
          }
        }

        // Source generated definition
        if (
          isSourceMatch &&
          edge.data().source_generated_definition &&
          edge.data().source_generated_definition !== 'nan'
        ) {
          const entitynametype = `${edge.data().originalsource} [${edge.data().sourcetype}]`;
          const definitionKey = createDefinitionKey(edge.data().source_generated_definition, pmidValue);
          if (!uniqueDefinitions.has(definitionKey)) {
            uniqueDefinitions.add(definitionKey);
            generatedDefinitions.push(`
              <li class="definition-item">
                <span class="definition-entity">${entitynametype}</span>
                <span class="definition-text">${edge.data().source_generated_definition}</span>
                <span class="definition-pmid">PMID: <a class="tooltippubmed-link tooltippubmed-hyperlink" href="javascript:void(0)"
                  data-pmid="${pmidValue}" data-source="${entitynametype}" data-interaction="${edge.data().interaction}"
                  data-target="${edge.data().originaltarget} [${edge.data().targettype}]" data-section="${sectionValue}">${pmidValue && sectionValue && pmidValue.endsWith('_' + sectionValue) ? pmidValue : (pmidValue + (sectionValue ? '_' + sectionValue : ''))}</a></span>
              </li>
            `);
          }
        }

        // Target generated definition
        if (
          isTargetMatch &&
          edge.data().target_generated_definition &&
          edge.data().target_generated_definition !== 'nan'
        ) {
          const entitynametype = `${edge.data().originaltarget} [${edge.data().targettype}]`;
          const definitionKey = createDefinitionKey(edge.data().target_generated_definition, pmidValue);
          if (!uniqueDefinitions.has(definitionKey)) {
            uniqueDefinitions.add(definitionKey);
            generatedDefinitions.push(`
              <li class="definition-item">
                <span class="definition-entity">${entitynametype}</span>
                <span class="definition-text">${edge.data().target_generated_definition}</span>
                <span class="definition-pmid">PMID: <a class="tooltippubmed-link tooltippubmed-hyperlink" href="javascript:void(0)"
                  data-pmid="${pmidValue}" data-source="${edge.data().originalsource} [${edge.data().sourcetype}]"
                  data-interaction="${edge.data().interaction}" data-target="${entitynametype}" data-section="${sectionValue}">${pmidValue && sectionValue && pmidValue.endsWith('_' + sectionValue) ? pmidValue : (pmidValue + (sectionValue ? '_' + sectionValue : ''))}</a></span>
              </li>
            `);
          }
        }
      }
    }

    renderDefinitions();

    function renderDefinitions() {
      extractedDefinitions = extractedDefinitions
        .filter((item) => !item.includes('nan'))
        .slice(0, 50);
      generatedDefinitions = generatedDefinitions
        .filter((item) => !item.includes('nan'))
        .slice(0, 50);

      if (found) {
        const numNodes = cy.nodes().length;
        const largeNetworkWarning = numNodes > 1000
          ? `<div class="large-network-banner">
              <span class="large-network-icon">&#9888;</span>
              <span class="large-network-text">
                The network below is large and might be difficult to interpret.
                Click on <em>'Node Filter'</em> to focus on a specific type of entities (genes, metabolites and others).
                Likewise, click on <em>'Edge Filter'</em>, to focus on specific relationships (regulates, interacts, localizes to).
              </span>
              <button class="large-network-close" onclick="this.parentElement.style.display='none'">&times;</button>
            </div>`
          : '';
        nodeSummary.innerHTML = `
          ${largeNetworkWarning}
          <div class="node-summary-line">
            <span class="lead">Node summary of the network:</span>
            <span class="node-summary-badge">Query nodes are <span class="hint-red">highlighted in red</span> and appear <strong>larger</strong> for easy identification.</span>
          </div>
        `;
        if (definitionsContainer) {
          definitionsContainer.innerHTML = `
            <div class="section-title">Entity Definitions</div>
            <div class="definitions-wrapper">
              <div class="definitions-panel" id="extractedDefinitionsContainer">
                <div class="definitions-panel-header extracted">Extracted Definitions</div>
                <div class="definitions-panel-body" id="extractedDefinitionsBody"></div>
              </div>
              <div class="definitions-panel" id="generatedDefinitionsContainer">
                <div class="definitions-panel-header generated">Generated Definitions</div>
                <div class="definitions-panel-body" id="generatedDefinitionsBody"></div>
              </div>
            </div>
            <div id="paginationControls"></div>
          `;
          showPage(1);
          // Show the card wrapper if it exists
          const defCard = document.getElementById('definitionsCard');
          if (defCard) defCard.style.display = '';
        }
      } else {
        nodeSummary.innerHTML = `<p></p>`;
        if (definitionsContainer) {
          definitionsContainer.innerHTML = '';
          const defCard = document.getElementById('definitionsCard');
          if (defCard) defCard.style.display = 'none';
        }
      }
    }

    function showPage(page) {
      const start = (page - 1) * itemsPerPage;
      const end = start + itemsPerPage;

      const totalPages = Math.ceil(
        Math.max(extractedDefinitions.length, generatedDefinitions.length) / itemsPerPage
      );

      const extractedBody = document.getElementById('extractedDefinitionsBody');
      const extractedContent = extractedDefinitions.slice(start, end).join('');
      extractedBody.innerHTML = extractedContent
        ? `<ul class="definitions-list">${extractedContent}</ul>`
        : '<p class="definitions-empty">No extracted definitions available.</p>';

      const generatedBody = document.getElementById('generatedDefinitionsBody');
      const generatedContent = generatedDefinitions.slice(start, end).join('');
      generatedBody.innerHTML = generatedContent
        ? `<ul class="definitions-list">${generatedContent}</ul>`
        : '<p class="definitions-empty">No generated definitions available.</p>';

      // Update page indicator in headers
      const extractedHeader = document.querySelector('.definitions-panel-header.extracted');
      const generatedHeader = document.querySelector('.definitions-panel-header.generated');
      if (extractedHeader) extractedHeader.textContent = `Extracted Definitions (${page}/${totalPages})`;
      if (generatedHeader) generatedHeader.textContent = `Generated Definitions (${page}/${totalPages})`;

      addPaginationControls(page);
    }

    function addPaginationControls(currentPage) {
      const paginationDiv = document.getElementById('paginationControls');
      paginationDiv.innerHTML = '';
      const totalPages = Math.ceil(
        Math.max(extractedDefinitions.length, generatedDefinitions.length) / itemsPerPage
      );

      if (totalPages <= 1) return;

      const nav = document.createElement('nav');
      nav.setAttribute('aria-label', 'Pagination');
      nav.className = 'definitions-pagination';
      const ul = document.createElement('ul');
      ul.className = 'definitions-page-list';

      // Previous button
      const prevLi = document.createElement('li');
      const prevLink = document.createElement('a');
      prevLink.textContent = '\u25C0';
      prevLink.href = '#';
      prevLink.className = 'def-page-link' + (currentPage === 1 ? ' disabled' : '');
      prevLink.onclick = (e) => { e.preventDefault(); if (currentPage > 1) showPage(currentPage - 1); };
      prevLi.appendChild(prevLink);
      ul.appendChild(prevLi);

      for (let i = 1; i <= totalPages; i++) {
        const li = document.createElement('li');
        const pageLink = document.createElement('a');
        pageLink.className = 'def-page-link' + (i === currentPage ? ' active' : '');
        pageLink.textContent = i;
        pageLink.href = '#';
        pageLink.onclick = (e) => {
          e.preventDefault();
          showPage(i);
        };
        li.appendChild(pageLink);
        ul.appendChild(li);
      }

      // Next button
      const nextLi = document.createElement('li');
      const nextLink = document.createElement('a');
      nextLink.textContent = '\u25B6';
      nextLink.href = '#';
      nextLink.className = 'def-page-link' + (currentPage === totalPages ? ' disabled' : '');
      nextLink.onclick = (e) => { e.preventDefault(); if (currentPage < totalPages) showPage(currentPage + 1); };
      nextLi.appendChild(nextLink);
      ul.appendChild(nextLi);

      nav.appendChild(ul);
      paginationDiv.appendChild(nav);
    }
  }

  /**
   *  Gather node categories that are checked
   */
  function getSelectedNodeCategories() {
    const nodeCategoryCheckboxes = document.querySelectorAll('input[data-category]:checked');
    return new Set(Array.from(nodeCategoryCheckboxes).map(cb => cb.value));
  }

  /**
   *  Gather edge interactions that are checked
   */
  function getSelectedEdgeTypes() {
    const container = document.getElementById('edgeTypeCheckboxes');
    const checkedBoxes = container.querySelectorAll('input[type="checkbox"]:checked');
    const selected = new Set(Array.from(checkedBoxes).map(cb => cb.value));
    return selected;
  }

  /**
   *  Combined filter: node categories + edge types
   */
  function applyAllFilters() {
    cy.startBatch();
  
    // 1) Which node categories are selected?
    const selectedCategories = getSelectedNodeCategories(); 
  
    // 2) Which edge interactions are selected?
    const selectedEdgeTypes = getSelectedEdgeTypes();

    // 3) Which edge categories are selected?
    const selectedEdgeCategories = getSelectedEdgeCategories();

    // 4) Hide everything first
    cy.nodes().hide();
    cy.edges().hide();

    // 5) Show nodes that pass node category OR are query nodes
    cy.nodes().forEach((node) => {
      const nodeCategory = getNodeCategory(node.data('type')?.toLowerCase() || '', node);
      if (
        selectedCategories.size === 0             // no category selected => show all
        || selectedCategories.has(nodeCategory)   // category is selected
        || isCentralNode(node)                 // always allow query‐term node
      ) {
        node.show();
      }
    });

    // 6) Show edges that match edge-type AND edge-category filters, with both endpoints visible
    cy.edges().forEach((edge) => {
      const interaction = edge.data('interaction')?.toLowerCase() || '';
      const edgeCategory = edge.data('category') || 'NA';
      const typePasses =
        selectedEdgeTypes.size === 0
        || selectedEdgeTypes.has(interaction);
      const categoryPasses =
        selectedEdgeCategories.size === 0
        || selectedEdgeCategories.has(edgeCategory);

      if (typePasses && categoryPasses && edge.source().visible() && edge.target().visible()) {
        edge.show();
      }
    });
  
    // 7) Finally, hide any visible node that ends up with no visible edges
    //    unless it's a central (query) node — those always stay visible
    cy.nodes(':visible').forEach((node) => {
      const isIsolated = node.connectedEdges(':visible').length === 0;
      if (isIsolated && !isCentralNode(node)) {
        node.hide();
      }
    });
  
    cy.endBatch();
  
    // Update counters, summaries, etc.
    updateNumNodes();
    updatePaperCount();
    updateNodeSummaries();
  }

  /**
   * Original createEdgeFilter logic replaced by dynamic edgeType listing
   */
  function initializeEdgeFilters(batchSize = 200) {
    const checkboxContainer = document.getElementById('edgeTypeCheckboxes');
    const edgesArray = cy.edges().toArray();
    const edgeCounts = {};
    let index = 0;

    function processEdgeBatch() {
      const start = index;
      const end = Math.min(index + batchSize, edgesArray.length);

      for (let i = start; i < end; i++) {
        const edge = edgesArray[i];
        const interactionType = edge.data().interaction.toLowerCase();
        if (!edgeCounts[interactionType]) {
          edgeCounts[interactionType] = 0;
        }
        edgeCounts[interactionType]++;
      }

      index += batchSize;
      if (index < edgesArray.length) {
        requestAnimationFrame(processEdgeBatch);
      } else {
        populateEdgeTypeCheckboxes(edgeCounts, checkboxContainer);
      }
    }
    requestAnimationFrame(processEdgeBatch);
  }

  function populateEdgeTypeCheckboxes(edgeCounts, checkboxContainer, batchSize = 50) {
    const sortedEdgeTypes = Object.keys(edgeCounts).sort((a, b) => edgeCounts[b] - edgeCounts[a]);
    let index = 0;
  
    function processCheckboxBatch() {
      const start = index;
      const end = Math.min(index + batchSize, sortedEdgeTypes.length);
  
      for (let i = start; i < end; i++) {
        const type = sortedEdgeTypes[i];
  
        const label = document.createElement('label');
        label.innerText = `${capitalizeFirstLetter(type)} (${edgeCounts[type]})`;
  
        const checkbox = document.createElement('input');
        checkbox.type = 'checkbox';
        checkbox.value = type;
        checkbox.setAttribute('data-type', type);
        checkbox.setAttribute('data-count', edgeCounts[type]); // so reorder can read data-count
  
        // On change => reorder and also apply filter
        checkbox.addEventListener('change', () => {
          handleCheckboxChange('edgeTypeCheckboxes');
          applyAllFilters();
        });
  
        label.prepend(checkbox);
        checkboxContainer.appendChild(label);
      }
  
      index += batchSize;
      if (index < sortedEdgeTypes.length) {
        requestAnimationFrame(processCheckboxBatch);
      } else {
        // Once we've appended all labels, reorder them initially:
        reorderCheckboxes('edgeTypeCheckboxes');
      }
    }
    requestAnimationFrame(processCheckboxBatch);
  }

  function capitalizeFirstLetter(string) {
    return string.charAt(0).toUpperCase() + string.slice(1);
  }

  /**
   * Node Category Filters
   */
  function initializeCategoryFilters(batchSize = 200) {
    const checkboxContainer = document.getElementById('nodeTypeCheckboxes');
    const categoryCounts = {};
    const nodesArray = cy.nodes().toArray();
    let index = 0;

    function processNodeBatch() {
      const start = index;
      const end = Math.min(index + batchSize, nodesArray.length);

      for (let i = start; i < end; i++) {
        const node = nodesArray[i];
        const category = getNodeCategory(node.data().type?.toLowerCase() || '', node);

        if (!categoryCounts[category]) {
          categoryCounts[category] = 0;
        }
        categoryCounts[category]++;
      }

      index += batchSize;
      if (index < nodesArray.length) {
        requestAnimationFrame(processNodeBatch);
      } else {
        populateCategoryCheckboxes(categoryCounts, checkboxContainer);
      }
    }
    requestAnimationFrame(processNodeBatch);
  }

  function populateCategoryCheckboxes(categoryCounts, checkboxContainer, batchSize = 50) {
    const sortedCategories = Object.keys(categoryCounts).sort((a, b) => categoryCounts[b] - categoryCounts[a]);
    let index = 0;

    function processCheckboxBatch() {
      const start = index;
      const end = Math.min(index + batchSize, sortedCategories.length);

      for (let i = start; i < end; i++) {
        const category = sortedCategories[i];
        const label = document.createElement('label');
        label.innerText = `${titleCaseCategory(category)} (${categoryCounts[category]})`;

        const checkbox = document.createElement('input');
        checkbox.type = 'checkbox';
        checkbox.value = category;
        checkbox.setAttribute('data-category', category);

        // When user toggles => re‐apply combined filter
        checkbox.addEventListener('change', () => {
          handleCheckboxChange('edgeTypeCheckboxes');  // reorder
          applyAllFilters();
        });

        label.prepend(checkbox);
        checkboxContainer.appendChild(label);
      }

      index += batchSize;
      if (index < sortedCategories.length) {
        requestAnimationFrame(processCheckboxBatch);
      }
    }
    requestAnimationFrame(processCheckboxBatch);
  }

  /**
   * Initialize Edge Category Filter checkboxes
   */
  function initializeEdgeCategoryFilters(batchSize = 200) {
    const checkboxContainer = document.getElementById('edgeCategoryCheckboxes');
    if (!checkboxContainer) return;
    const edgesArray = cy.edges().toArray();
    const categoryCounts = {};
    let index = 0;

    function processEdgeBatch() {
      const start = index;
      const end = Math.min(index + batchSize, edgesArray.length);
      for (let i = start; i < end; i++) {
        const cat = edgesArray[i].data('category') || 'NA';
        if (!categoryCounts[cat]) categoryCounts[cat] = 0;
        categoryCounts[cat]++;
      }
      index += batchSize;
      if (index < edgesArray.length) {
        requestAnimationFrame(processEdgeBatch);
      } else {
        const sorted = Object.keys(categoryCounts).sort((a, b) => categoryCounts[b] - categoryCounts[a]);
        sorted.forEach(cat => {
          const label = document.createElement('label');
          label.innerText = `${titleCaseCategory(cat)} (${categoryCounts[cat]})`;
          const checkbox = document.createElement('input');
          checkbox.type = 'checkbox';
          checkbox.value = cat;
          checkbox.setAttribute('data-edgecategory', cat);
          checkbox.addEventListener('change', () => { applyAllFilters(); });
          label.prepend(checkbox);
          checkboxContainer.appendChild(label);
        });
      }
    }
    requestAnimationFrame(processEdgeBatch);
  }

  /**
   * Gather selected edge categories
   */
  function getSelectedEdgeCategories() {
    const container = document.getElementById('edgeCategoryCheckboxes');
    if (!container) return new Set();
    const checkedBoxes = container.querySelectorAll('input[type="checkbox"]:checked');
    return new Set(Array.from(checkedBoxes).map(cb => cb.value));
  }

  /**
   * Web worker logic for metrics calculation
   */
  const workerCode = `
    self.onmessage = function (e) {
      try {
        console.log("Worker received data");
        const elements = e.data.elements;
        if (!elements || !Array.isArray(elements.nodes) || !Array.isArray(elements.edges)) {
          throw new Error("Invalid elements: nodes or edges array is missing.");
        }
        console.time("Worker Metrics Calculation Time");
        const result = computeNodeMetrics(elements);
        console.timeEnd("Worker Metrics Calculation Time");
        console.log("Worker finished processing.");
        postMessage(result);
      } catch (err) {
        console.error("Worker error:", err);
        postMessage({ error: err.message });
      }
    };

    function computeNodeMetrics(elements) {
      console.log("Calculating node degrees and clustering coefficients...");
      const degreeMap = {};
      const clusteringMap = {};

      elements.nodes.forEach((node) => {
        degreeMap[node.data.id] = 0;
        clusteringMap[node.data.id] = { neighbors: [] };
      });

      elements.edges.forEach((edge) => {
        const { source, target } = edge.data;
        degreeMap[source] = (degreeMap[source] || 0) + 1;
        degreeMap[target] = (degreeMap[target] || 0) + 1;

        clusteringMap[source].neighbors.push(target);
        clusteringMap[target].neighbors.push(source);
      });

      Object.entries(clusteringMap).forEach(([nodeId, { neighbors }]) => {
        const degree = degreeMap[nodeId];
        if (degree < 2) {
          clusteringMap[nodeId].coefficient = 0;
        } else {
          let connectedNeighbors = 0;
          neighbors.forEach((neighbor, i) => {
            for (let j = i + 1; j < neighbors.length; j++) {
              if (clusteringMap[neighbors[j]].neighbors.includes(neighbor)) {
                connectedNeighbors++;
              }
            }
          });
          clusteringMap[nodeId].coefficient = (2 * connectedNeighbors) / (degree * (degree - 1));
        }
      });

      console.log("Node metrics calculation complete.");
      return { degreeMap, clusteringCoefficients: clusteringMap };
    }
  `;
  // Web worker code is defined above but not currently used for layout.
  // Workers removed to avoid spawning unused threads.

  /**
   * Layout logic
   */
  function applyLayout() {
    const loadingEl = document.getElementById('layout-loading');
    if (loadingEl) loadingEl.style.display = 'flex';
    console.log('Starting layout...');
    // Skip random pre-positioning — cose/fcose handle it with randomize: true
    finalizeRandomLayout();
  }

  function applyRandomLayoutInBatches(batchSize = 100, graphWidth = 10000, graphHeight = 10000, minSpacing = 50) {
    const nodes = cy.nodes();
    const numBatches = Math.ceil(nodes.length / batchSize);
  
    function processBatch(batchIndex) {
      // If we've processed all batches, finalize the layout.
      if (batchIndex >= numBatches) {
        finalizeRandomLayout();
        return;
      }
  
      // If this is the last batch, include the "deciding layout" message.
      if (batchIndex === numBatches - 1) {
        console.log(`Processing random layout batch ${batchIndex + 1} of ${numBatches}, applying layout based on graph size...`);
      } else {
        console.log(`Processing random layout batch ${batchIndex + 1} of ${numBatches}...`);
      }
  
      const startIndex = batchIndex * batchSize;
      const endIndex = Math.min((batchIndex + 1) * batchSize, nodes.length);
      const nodeBatch = nodes.slice(startIndex, endIndex);
  
      nodeBatch.forEach((node) => {
        let randomX;
        let randomY;
        let isValid = false;
        while (!isValid) {
          randomX = Math.random() * graphWidth;
          randomY = Math.random() * graphHeight;
  
          isValid = !nodes.some((otherNode) => {
            if (node.id() === otherNode.id()) return false;
            const dx = otherNode.position('x') - randomX;
            const dy = otherNode.position('y') - randomY;
            return Math.sqrt(dx * dx + dy * dy) < minSpacing;
          });
        }
        node.position({ x: randomX, y: randomY });
      });
  
      // Schedule the next batch with a minimal delay
      setTimeout(() => processBatch(batchIndex + 1), 0);
    }
  
    processBatch(0);
  }

  function finalizeRandomLayout() {
    const numNodes = cy.nodes().length;

    const layoutOptions = {
      fit: true,
      padding: 50,
    };

    let layout = null;

    const numEdges = cy.edges().length;
    const density = numEdges / Math.max(numNodes, 1);  // edges per node

    // Dynamic layout parameters scale with graph size and density
    console.log(`Graph: ${numNodes} nodes, ${numEdges} edges, density=${density.toFixed(1)}`);

    // Edge length from slider (default 120), used directly as idealEdgeLength
    const userEdgeLen = parseInt(document.getElementById('vs-edge-len')?.value || 120);
    const edgeLenMult = userEdgeLen / 120;  // 1x at default

    // fcose params scaled by graph size and user edge length
    const repulsion = (numNodes <= 200 ? 12000 : numNodes <= 500 ? 8000 : 6000) * edgeLenMult;
    const edgeLen = userEdgeLen;
    const grav = numNodes <= 200 ? 0.15 : numNodes <= 500 ? 0.3 : 0.6;
    const animate = numNodes <= 200;
    // Always use 'default' quality — 'draft' produces broken layouts
    const quality = 'default';

    console.log(`fcose: nodes=${numNodes}, edges=${numEdges}, repulsion=${repulsion.toFixed(0)}, edgeLen=${edgeLen.toFixed(0)}, gravity=${grav.toFixed(2)}, animate=${animate}`);

    layout = cy.layout({
      ...layoutOptions,
      name: 'fcose',
      animate: animate,
      animationDuration: animate ? 800 : 0,
      quality: quality,
      randomize: true,
      nodeRepulsion: () => repulsion,
      idealEdgeLength: () => edgeLen,
      edgeElasticity: () => 0.45,
      gravity: grav,
      gravityRange: 3.8,
      nodeDimensionsIncludeLabels: true,
      sampleSize: numNodes > 500 ? 100 : 25,
    });

    layout.on('layoutstart', () => console.log(`${layout.options.name} layout started...`));
    layout.on('layoutready', () => {
      console.log('Layout ready.');
      cy.fit();
    });
    layout.on('layoutstop', () => {
      console.log('Layout completed.');
      const positions = cy.nodes().map(n => n.position());
      const allSame = positions.length > 1 && positions.every(p => Math.abs(p.x - positions[0].x) < 1 && Math.abs(p.y - positions[0].y) < 1);
      if (allSame) {
        console.warn('Layout collapsed — falling back to circle.');
        cy.layout({ name: 'circle', fit: true, padding: 40 }).run();
      }
      if (window.VS) VS._onLayoutDone(document.getElementById('layout-loading'));
      updateNodeSummaries();
    });

    try {
      layout.run();
    } catch (e) {
      console.error('fcose layout error, falling back to circle:', e);
      cy.layout({ name: 'circle', fit: true, padding: 40 }).run();
      cy.fit(cy.elements(), 40);
      styleCentralNodes(queryTerm);
      const loadingEl = document.getElementById('layout-loading');
      if (loadingEl) loadingEl.style.display = 'none';
    }

    // Safety fallback: hide overlay after 15s in case layoutstop doesn't fire
    setTimeout(() => {
      const loadingEl = document.getElementById('layout-loading');
      if (loadingEl && loadingEl.style.display !== 'none') {
        loadingEl.style.display = 'none';
        cy.fit(cy.elements(), 40);
        cy.center();
        styleCentralNodes(queryTerm);
        updateNodeSummaries();
      }
    }, 15000);

    // Recenter on window resize
    window.addEventListener('resize', () => { cy.resize(); cy.fit(cy.elements(), 40); });
  }

  /**
   * Initialization of the entire application
   */
  function initializeApp() {
    initializeEventListeners();
    // Build checkboxes for edge types (based on actual edges):
    initializeEdgeFilters();
    // Build checkboxes for node categories (based on actual nodes):
    initializeCategoryFilters();
    // Build checkboxes for edge categories:
    initializeEdgeCategoryFilters();
    // ══════════════════════════════════════════════════
    // View Settings (VS)
    // ══════════════════════════════════════════════════
    const VS = {
      baseline: {},

      saveBaseline() {
        this.baseline = {};
        cy.nodes().forEach(n => { const p = n.position(); this.baseline[n.id()] = { x: p.x, y: p.y }; });
      },

      restoreBaseline() {
        cy.startBatch();
        cy.nodes().forEach(n => { const b = this.baseline[n.id()]; if (b) n.position(b); });
        cy.endBatch();
      },

      set(key, val) {
        const v = parseFloat(val);
        const labelMap = { nodeSize: 'node-size', fontSize: 'font-size', edgeFontSize: 'edge-font', overlap: 'overlap' };
        const lbl = document.getElementById('vs-' + (labelMap[key] || key) + '-val');
        if (lbl) lbl.textContent = val;

        switch (key) {
          case 'nodeSize':
            cy.startBatch();
            cy.nodes().forEach(n => {
              const s = queryTerm.some(t => n.id() === t) ? v * 1.3 : v;
              n.style({ width: s, height: s });
            });
            cy.endBatch();
            break;
          case 'fontSize':
            cy.nodes().style('font-size', v + 'px');
            break;
          case 'edgeFontSize':
            cy.edges().style(v === 0
              ? { 'min-zoomed-font-size': 9999 }
              : { 'font-size': v + 'px', 'min-zoomed-font-size': 1 });
            break;
          case 'overlap':
            this._deoverlap(v);
            break;
          case 'edgeLength':
            // Debounce: re-run layout 500ms after user stops dragging
            clearTimeout(window._edgeLenTimer);
            window._edgeLenTimer = setTimeout(() => this.applyLayout(), 500);
            break;
        }
      },

      _deoverlap(strength) {
        // Always restore baseline first so slider is bidirectional
        this.restoreBaseline();
        if (strength <= 0) { cy.fit(cy.elements(':visible'), 40); return; }

        const extra = strength * 0.8;
        const iters = Math.ceil(3 + strength * 0.12);
        const nodes = cy.nodes(':visible').toArray();
        const fs = parseFloat(cy.nodes().first()?.style('font-size')) || 14;
        const cw = fs * 0.55;

        cy.startBatch();
        for (let it = 0; it < iters; it++) {
          for (let i = 0; i < nodes.length; i++) {
            const a = nodes[i], pa = a.position();
            const wA = Math.max(a.width(), (a.data('originalId') || '').length * cw) + extra;
            const hA = a.height() + fs + 6 + extra;
            for (let j = i + 1; j < nodes.length; j++) {
              const b = nodes[j], pb = b.position();
              const wB = Math.max(b.width(), (b.data('originalId') || '').length * cw) + extra;
              const hB = b.height() + fs + 6 + extra;
              const dx = pb.x - pa.x, dy = pb.y - pa.y;
              const mx = (wA + wB) / 2, my = (hA + hB) / 2;
              if (Math.abs(dx) < mx && Math.abs(dy) < my) {
                const ox = mx - Math.abs(dx), oy = my - Math.abs(dy);
                if (ox < oy) {
                  const p = ox / 2 + 1, s = dx >= 0 ? 1 : -1;
                  a.position({ x: pa.x - s * p, y: pa.y }); b.position({ x: pb.x + s * p, y: pb.y });
                } else {
                  const p = oy / 2 + 1, s = dy >= 0 ? 1 : -1;
                  a.position({ x: pa.x, y: pa.y - s * p }); b.position({ x: pb.x, y: pb.y + s * p });
                }
              }
            }
          }
        }
        cy.endBatch();
        cy.fit(cy.elements(':visible'), 40);
      },

      applyLayout() {
        applyAllFilters();
        const name = document.getElementById('vs-layout')?.value || 'fcose';
        const loadingEl = document.getElementById('layout-loading');
        if (loadingEl) loadingEl.style.display = 'flex';

        if (name === 'fcose') { applyLayout(); return; }

        const n = cy.nodes(':visible').length;
        const uel = parseInt(document.getElementById('vs-edge-len')?.value || 80);
        const opts = { name, fit: true, padding: 40, randomize: true, animate: n <= 200, animationDuration: 600 };
        if (name === 'cose') Object.assign(opts, { nodeRepulsion: 400000 * (uel/80), idealEdgeLength: uel, gravity: 80, numIter: 100, animate: n <= 120 });
        if (name === 'concentric') { opts.concentric = nd => nd.degree(); opts.levelWidth = () => 2; }
        if (name === 'breadthfirst') { opts.directed = true; opts.spacingFactor = 1.2; }

        const layout = cy.layout(opts);
        layout.on('layoutstop', () => this._onLayoutDone(loadingEl));
        layout.run();
        setTimeout(() => { if (loadingEl) loadingEl.style.display = 'none'; }, 15000);
      },

      _onLayoutDone(loadingEl) {
        this.saveBaseline();
        styleCentralNodes(queryTerm);
        if (loadingEl) loadingEl.style.display = 'none';
        const s = document.getElementById('vs-overlap');
        if (s) { s.value = 0; document.getElementById('vs-overlap-val').textContent = '0'; }
        cy.fit(cy.elements(':visible'), 40);
        updateNodeSummaries();
      },

      fit() { cy.fit(cy.elements(':visible'), 40); cy.center(); },

      reset() {
        this.restoreBaseline();
        const defs = { 'vs-node-size': 55, 'vs-font-size': 11, 'vs-edge-font': 8, 'vs-overlap': 0, 'vs-edge-len': 120 };
        for (const [id, v] of Object.entries(defs)) {
          const el = document.getElementById(id); if (el) el.value = v;
          const lbl = document.getElementById(id + '-val'); if (lbl) lbl.textContent = v;
        }
        const sel = document.getElementById('vs-layout'); if (sel) sel.value = 'fcose';
        cy.nodes().forEach(n => {
          const s = queryTerm.some(t => n.id() === t) ? 70 : 55;
          n.style({ width: s, height: s, 'font-size': '11px' });
        });
        cy.edges().style({ 'font-size': '8px', 'min-zoomed-font-size': 1 });
        styleCentralNodes(queryTerm);
        cy.fit(cy.elements(':visible'), 40);
      },
    };
    window.VS = VS;
    window.toggleViewSettings = function() {
      const p = document.getElementById('viewSettingsPanel');
      p.style.display = p.style.display === 'none' ? 'block' : 'none';
    };
    window.recalculateLayout = function() { VS.applyLayout(); };
    window.fitGraph = function() { VS.fit(); };
  }

    applyLayout();
    resetNetworkView();
    showDefinitionsForSearchTerm(queryTerm);
    styleCentralNodes(queryTerm);
    updateNodeSummaries();

    // Let nodes be grabbed if desired
    cy.autoungrabify(false);


  /**
   * On DOM ready, initialize the app
   */
  document.addEventListener('DOMContentLoaded', () => {
    initializeApp();
  });
