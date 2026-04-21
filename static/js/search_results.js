/*
This file contains the original JavaScript contained inside gene.html (i.e., inside those <script> tags).
I've taken them out and dumped them into a JavaScript file for the sake of organization (so that the code
doesn't look too bloated and is more maintainable in the long run).
*/

var searchForm = document.getElementById("node-search-form");
searchForm.addEventListener("submit", function (event) {
  event.preventDefault();
  const searchTerm = event.target[0].value.trim().toLowerCase();
  const cy = document.getElementById("cy")._cyreg.cy;

  // Clear previous highlight styles
  cy.nodes().removeStyle("opacity border-width border-color overlay-color overlay-padding overlay-opacity");
  cy.edges().removeStyle("opacity");

  if (!searchTerm) return;

  // Substring match against both the display label (originalId) and the full id
  const matchingNodes = cy.nodes().filter(function (node) {
    const nodeId = (node.id() || "").toLowerCase();
    const label = (node.data("originalId") || node.data("label") || "").toLowerCase();
    return nodeId.includes(searchTerm) || label.includes(searchTerm);
  });

  if (matchingNodes.length === 0) {
    alert(`No nodes found matching "${searchTerm}"`);
    return;
  }

  // Dim everything strongly; highlight matches with full opacity + yellow halo border
  cy.nodes().style({ "opacity": 0.15 });
  cy.edges().style({ "opacity": 0.08 });

  matchingNodes.style({
    "opacity": 1,
    "border-width": 4,
    "border-color": "#FFD700",
    "overlay-color": "#FFD700",
    "overlay-padding": 8,
    "overlay-opacity": 0.35,
  });

  // Also brighten edges connected to matches so context is visible
  matchingNodes.connectedEdges().style({ "opacity": 0.7 });

  // Center/zoom on matches
  cy.animate({ fit: { eles: matchingNodes, padding: 80 }, duration: 400 });
});

// {{ cytoscape_js_code | safe }} --> meant to be put into the script file this originally belonged in.
/*
function recalculateLayout(batchSize = 200) {
  const cy = document.getElementById("cy")._cyreg.cy;
  const visibleNodes = cy.elements(":visible");
  const numBatches = Math.ceil(visibleNodes.nodes().length / batchSize);  // Calculate number of batches
  let processedBatches = 0;

  cy.startBatch();  // Start batching operations for better performance

  // Function to process each batch
  function processBatch(batchIndex) {
    const batchStart = batchIndex * batchSize;
    const batchEnd = Math.min(batchStart + batchSize, visibleNodes.nodes().length);
    const nodeBatch = visibleNodes.nodes().slice(batchStart, batchEnd);
    const edgeBatch = visibleNodes.edges().filter(edge => {
      const sourceId = edge.data('source');
      const targetId = edge.data('target');
      return nodeBatch.some(node => node.id() === sourceId || node.id() === targetId);
    });

    const elements = {
      nodes: nodeBatch.map(node => ({
        id: node.id(),
        position: node.position()
      })),
      edges: edgeBatch.map(edge => ({
        source: edge.data('source'),
        target: edge.data('target')
      }))
    };

    // Send the elements and layout type to the worker
    layoutWorker.postMessage({
      elements: elements,
      type: 'cose'  // You can change this to 'random' if needed
    });

    // Listen for the worker's response for each batch
    layoutWorker.onmessage = function(e) {
      const processedElements = e.data;

      // Update node positions with the processed positions from the worker
      processedElements.nodes.forEach(nodeData => {
        const node = cy.getElementById(nodeData.id);
        if (node && nodeData.position) {
          node.position(nodeData.position);
        }
      });

      // Use requestAnimationFrame for smoother updates when applying layouts
      requestAnimationFrame(() => {
        // Once the batch is processed, apply the layout for the current batch
        const layout = nodeBatch.union(edgeBatch).layout({
          name: "cose",
          animate: false,
          randomize: false,  // Don't randomize, keep previous positions
          idealEdgeLength: 100,
          nodeOverlap: 50,
          refresh: 50,
          numIter: 500,
          fit: false,  // Disable auto-fit for each batch
          padding: 10,
          boundingBox: { x1: 0, y1: 0, w: 1000, h: 1000 }  // Constrain layout within a box
        });

        layout.run();

        // Process the next batch if there are more
        processedBatches++;
        if (processedBatches < numBatches) {
          processBatch(processedBatches);  // Recursive call to process the next batch
        } else {
          // After all batches are processed, apply a final layout to refine the overall structure
          requestAnimationFrame(() => {
            const finalLayout = cy.layout({
              name: 'cose',   // You can use 'cose' or 'fcose' for better results
              animate: false,
              randomize: false,  // Keep current node positions
              idealEdgeLength: 100,
              nodeOverlap: 50,
              refresh: 50,
              numIter: 1000,  // Allow more iterations for the final layout
              fit: true,      // Fit the entire graph after the final layout
              padding: 20
            });

            finalLayout.run();
            cy.endBatch();  // End the batching operations after all batches and final layout
          });
        }
      });
    };
  }

  // Start processing the first batch
  processBatch(0);
}
*/

function recalculateLayout() {
  // Apply all checkbox filters first (node category + edge type + edge category)
  if (typeof applyAllFilters === 'function') {
    applyAllFilters();
  }

  const cy = document.getElementById("cy")._cyreg.cy;

  // Get visible nodes and edges
  const visibleNodes = cy.nodes(":visible").filter(node => node.degree() > 0); // Exclude disconnected nodes
  const visibleEdges = cy.edges(":visible");
  const visibleElements = visibleNodes.union(visibleEdges);

  const numNodes = visibleNodes.length;
  console.log(`Recalculating layout for ${numNodes} visible nodes...`);

  let layout;
  if (numNodes < 1000) {
    console.log('Applying COSE layout...');
    layout = visibleElements.layout({
      name: "cose",
      // Whether to animate while running the layout
      animate             : true,

      // Number of iterations between consecutive screen positions update (0 -> only updated on the end)
      refresh             : 4,
      
      // Whether to fit the network view after when done
      fit                 : true, 

      // Padding on fit
      padding             : 30, 

      // Constrain layout bounds; { x1, y1, x2, y2 } or { x1, y1, w, h }
      boundingBox         : undefined,

      // Whether to randomize node positions on the beginning
      randomize           : true,
      
      // Whether to use the JS console to print debug messages
      debug               : false,

      // Node repulsion (non overlapping) multiplier
      nodeRepulsion       : 200000,
      
      // Node repulsion (overlapping) multiplier
      nodeOverlap         : 10,
      
      // Ideal edge (non nested) length
      idealEdgeLength     : 10,
      
      // Divisor to compute edge forces
      edgeElasticity      : 100,
      
      // Nesting factor (multiplier) to compute ideal edge length for nested edges
      nestingFactor       : 5, 
      
      // Gravity force (constant)
      gravity             : 250, 
      
      // Maximum number of iterations to perform
      numIter             : 100,
      
      // Initial temperature (maximum node displacement)
      initialTemp         : 200,
      
      // Cooling factor (how the temperature is reduced between consecutive iterations
      coolingFactor       : 0.95, 
      
      // Lower temperature threshold (below this point the layout will end)
      minTemp             : 1.0
    });
  } else {
    console.log('Applying FCOSE layout...');
    layout = visibleElements.layout({
      name: 'fcose',
      quality: 'proof', // Use proof quality for better precision
      randomize: true, // Randomize initial positions
      animate: false, // Disable animation for performance
      fit: true, // Fit the graph into the viewport
      padding: 30, // Add extra padding around the graph
      nodeRepulsion: 10000, // Increase repulsion to push nodes apart
      edgeElasticity: 0.5, // Fine-tune elasticity for smoother edges
      nestingFactor: 0.1, // Helps with nested nodes
      gravityRangeCompound: 2.0, // Avoid overlapping compound nodes
      gravity: 0.1, // Lower gravity to reduce unnecessary attraction
      minNodeSpacing: 50, // Set minimum spacing between nodes
      nodeDimensionsIncludeLabels: true, // Ensure label size is included in spacing
    });
  }

  const loadingEl = document.getElementById('layout-loading');
  if (loadingEl) loadingEl.style.display = 'flex';
  layout.one('layoutstop', () => {
    if (loadingEl) loadingEl.style.display = 'none';
    // Re-apply central node styles after layout recalculation
    if (typeof styleCentralNodes === 'function' && typeof queryTerm !== 'undefined') {
      styleCentralNodes(queryTerm);
    }
  });
  layout.run(); // Apply the selected layout
}

/*
function recalculateLayout() {
  const numNodes = cy.nodes().length;

  cy.startBatch(); // Start batch for all layout operations
    // Use workers to preprocess nodes for COSE layout (500 nodes or less)
    layoutWorkersForCose();


  cy.endBatch(); // End batch after applying layout
}

// Function to use multiple workers for COSE layout
function layoutWorkersForCose() {
  const nodes = cy.nodes(':visible');
  const edges = cy.edges(':visible');

  const elements = prepareWorkerElements(nodes, edges);
  const numBatches = Math.ceil(nodes.length / (numWorkers * 100)); // Adjust based on worker count

  let processedBatches = 0;

  for (let i = 0; i < numBatches; i++) {
    const batchStart = i * (numWorkers * 100);
    const batchEnd = Math.min(batchStart + (numWorkers * 100), nodes.length);
    const nodeBatch = nodes.slice(batchStart, batchEnd);

    workers.forEach((worker, index) => {
      const workerBatch = nodeBatch.slice(index * 100, (index + 1) * 100); // Each worker gets a part of the batch
      if (workerBatch.length > 0) {
        worker.postMessage({
          type: 'cose',
          elements: prepareWorkerElementsForBatch(workerBatch, edges)
        });
      }
    });

    processedBatches++;
  }

  workers.forEach(worker => {
    worker.onmessage = function (e) {
      applyCoseLayout(e.data);
      processedBatches--;
      if (processedBatches === 0) {
        finalizeCoseLayout(); // Call finalize after all batches processed
      }
    };
  });
}

// Prepare data to send to the worker
function prepareWorkerElements(nodes, edges) {
  return {
    nodes: nodes.map(node => ({
      id: node.id(),
      position: node.position(),
    })),
    edges: edges.map(edge => ({
      source: edge.data('source'),
      target: edge.data('target'),
      id: edge.id(),
    }))
  };
}

// Prepare batch data to send to the worker
function prepareWorkerElementsForBatch(nodeBatch, edges) {
  return {
    nodes: nodeBatch.map(node => ({
      id: node.id(),
      position: node.position(),
    })),
    edges: edges.filter(edge => {
      const sourceId = edge.data('source');
      const targetId = edge.data('target');
      return nodeBatch.some(node => node.id() === sourceId || node.id() === targetId);
    }).map(edge => edge.data())
  };
}

// Apply layout (COSE) after preprocessing
function applyCoseLayout(data) {
  // Update node positions with the processed positions from the worker
  data.nodes.forEach(nodeData => {
    const node = cy.getElementById(nodeData.id);
    if (node) {
      node.position({ x: nodeData.position.x, y: nodeData.position.y });
    }
  });
}

// Finalize the COSE layout after all workers are done
function finalizeCoseLayout() {
  const layoutOptions = getCoseLayout2();
  const layout = cy.layout(layoutOptions);
  layout.run();
}

// Function to get COSE layout options
function getCoseLayout2() {
  return {
    name: 'cose',
    animate: true,
    fit: true,
    idealEdgeLength: 200,         // Increase ideal edge length for fewer adjustments
    refresh: 50,                  // Reduce refresh frequency to save computation
    numIter: 500,                // Reduce the number of iterations to make it less expensive
    randomize: false,             // Use existing positions to minimize recalculation
    nodeOverlap: 50,              // Allow more overlap to reduce complexity
    padding: 10,
    nodeDimensionsIncludeLabels: true
  };
}
*/
function decodeHTMLEntities(text) {
  var textArea = document.createElement("textarea");
  textArea.innerHTML = text;
  return textArea.value;
}

function downloadTableAsTSV(filename) {
  let tsvContent = "Source\tSource Type\tInteraction Type\tTarget\tTarget Type\tSection\tPubmed ID\tSpecies\tBasis\tSource_extracted_definition\tSource_generated_definition\tTarget_extracted_definition\tTarget_generated_definition\n";
  var decoded = decodeHTMLEntities(g).replace(
    /'(\b(?:id|idtype|target|targettype|inter_type|publication|p_source|species|basis|source_extracted_definition|source_generated_definition|target_extracted_definition|target_generated_definition\n";)\b)':/g,
    '"$1":'
  );
  decoded = decoded.replace(/:\s*'([^']+)'/g, function (match, capture) {
    return ': "' + capture.replace(/"/g, '\\"') + '"';
  });
  decoded = decoded.replace(/'target_generated_definition'/g, '"target_generated_definition"');
  console.log(decoded);
  var g_list = JSON.parse(decoded);
  g_list.forEach((item) => {
    tsvContent +=
      item["id"] +
      "\t" +
      item["idtype"] +
      "\t" +
      item["inter_type"] +
      "\t" +
      item["target"] +
      "\t" +
      item["targettype"] +
      "\t" +
      item["p_source"].toUpperCase()+
      "\t" +
      item["publication"] +
      "\t" +
      item["species"] +
      "\t" +
      item["basis"]+
      "\t" +
      item["source_extracted_definition"]+
      "\t" +
      item["source_generated_definition"]+
      "\t" +
      item["target_extracted_definition"]+
      "\t" +
      item["target_generated_definition"]+
      "\n";
  });
  const blob = new Blob([tsvContent], { type: "text/tab-separated-values" });
  const url = URL.createObjectURL(blob);

  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  link.click();
  URL.revokeObjectURL(url);
}

function downloadAsSVG() {
  // Assuming your Cytoscape instance is named 'cy'
  const cy = document.getElementById("cy")._cyreg.cy;

  // Register the SVG Exporter plugin
  cytoscape.use(cytoscapeSvg);

  // Export the network view as an SVG
  const svgContent = cy.svg({ copyStyles: true, bg: "white" });

  // Modify the downloaded SVG to have black letters
  const svgDOM = new DOMParser().parseFromString(svgContent, "image/svg+xml");
  const labels = svgDOM.querySelectorAll("text");
  labels.forEach((label) => label.setAttribute("fill", "#000000"));
  const modifiedSvgContent = new XMLSerializer().serializeToString(svgDOM);

  // Create a Blob from the SVG content
  const blob = new Blob([modifiedSvgContent], {
    type: "image/svg+xml;charset=utf-8",
  });
  const url = URL.createObjectURL(blob);

  // Create a link element, set its href to the Blob URL, and trigger a click event to download the SVG
  const link = document.createElement("a");
  link.href = url;
  link.download = "network.svg";
  link.click();

  // Revoke the Blob URL
  URL.revokeObjectURL(url);
}

document
  .getElementById("download-pdf")
  .addEventListener("click", downloadAsSVG);

function sortTable(table, column, asc = true) {
  const directionModifier = asc ? 1 : -1;
  const rows = Array.from(table.tBodies[0].querySelectorAll("tr"));

  const sortedRows = rows.sort((a, b) => {
    const aColText = a
      .querySelector(`td:nth-child(${column + 1})`)
      .textContent.trim();
    const bColText = b
      .querySelector(`td:nth-child(${column + 1})`)
      .textContent.trim();

    return aColText.localeCompare(bColText) * directionModifier;
  });

  while (table.tBodies[0].firstChild) {
    table.tBodies[0].removeChild(table.tBodies[0].firstChild);
  }
  table.tBodies[0].append(...sortedRows);

  table.setAttribute("data-sort-direction", asc ? "asc" : "desc");
  table.setAttribute("data-sort-column", column);
}

document.querySelectorAll(".sortable thead th").forEach((headerCell) => {
  headerCell.addEventListener("click", () => {
    const table = headerCell.parentElement.parentElement.parentElement;
    const columnIndex = Array.from(headerCell.parentElement.children).indexOf(
      headerCell
    );
    const currentDirection =
      table.getAttribute("data-sort-direction") === "asc" ? true : false;
    sortTable(table, columnIndex, !currentDirection);
  });
});
$(window).on("load", function () {
  const cy = document.getElementById("cy_wrapper");
  cy.style.height = `${window.innerHeight * 0.8}px`;
});
