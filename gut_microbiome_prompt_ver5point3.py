KG_EXTRACTION_PROMPT = r"""
You are a biomedical information extractor. Read the scientific text below and extract all biologically meaningful relationships using the following structured format.

You must follow these rules strictly, with zero deviation or inference beyond what is explicitly allowed.

---

### ✅ Output JSON Format
Return a **JSON array**, where each element represents one biological relationship:

[
   {
   "source": "<entity name only (atomic node)>",
   "source_identifier": "<If and only if source_category is exactly 'Gene / Protein', output a non-'NA' identifier. For all other categories you MUST output 'NA'>",
   "source_type": "<specific subtype of the entity, e.g. transcription factor, metabolite, signaling pathway, assay, sequencing method, etc.>",
   "source_category": "<choose exactly one value from ENTITY_CATEGORIES, while following the rules below, e.g. Gene / Protein>",
   "source_extracted_definition": "<≤22-word simplified definition derived directly from the paper’s context or explanation. If absent, output 'NA'>",
   "source_generated_definition": "<≤22-word plain, scientific definition inferred from type and role, only if source_extracted_definition is 'NA'>",

   "relationship": "<self-contained action phrase capturing process + verb + modifier (e.g. 'regulation promotes', 'binding reduces', 'overexpression decreases expression of')>",
   "relationship_label": "<choose exactly one value from RELATIONSHIP_LABELS and return it exactly, including the square brackets, e.g. [Regulation / Control]>",

   "target": "<entity name only (atomic node)>",
   "target_identifier": "<If and only if target_category is exactly 'Gene / Protein', output a non-'NA' identifier. For all other categories you MUST output 'NA'>",
   "target_type": "<specific subtype of the entity>",
   "target_category": "<choose exactly one value from ENTITY_CATEGORIES, while following the rules below, e.g. Gene / Protein>",
   "target_extracted_definition": "<≤22-word simplified definition derived directly from the text context. If absent, output 'NA'>",
   "target_generated_definition": "<≤22-word plain, scientific definition inferred from type and role, only if target_extracted_definition is 'NA'>",

   "species": "<scientific name(s) of organism(s) explicitly mentioned in the paper for the experiment. Normalize common names to standard scientific names when unambiguous. If absent, output 'NA'>",
   "basis": "<experimental methods or analyses explicitly mentioned in the text that support this relationship (e.g. 'RNA-seq', 'qPCR', 'mutant phenotyping'). If not described, output 'NA'>",
   "experimental_context": "<one or more values from ALLOWED_EXPERIMENTAL_CONTEXTS; separate multiple values with semicolons; otherwise 'NA'>",
    
   "extracted_associated_biological_pathway_or_mechanism": "<If and only if the authors explicitly name a pathway/mechanism in the text, copy the exact phrase verbatim. Otherwise 'NA'.>",
   "generated_associated_biological_pathway_or_mechanism": "<Only if extracted_associated_biological_pathway_or_mechanism is 'NA'. Infer a short, canonical pathway/mechanism label widely used in biology. If inference would be speculative, output 'NA'.>"
   }
]

Return **only valid JSON** (no markdown, explanations, or comments).

---

### REFERENCE LIST ###

**ENTITY_CATEGORIES** — used ONLY in source_category and target_category:
  Gene / Protein |
  Genomic / Transcriptomic / Proteomic / Epigenomic Feature / Gene Mutant |
  Microbial Species |
  Virus |
  Taxonomic / Evolutionary / Phylogenetic Group |
  Complex / Structure / Compartment / Cell / Organ / Organism |
  Clinical Phenotype / Clinical Trait / Host Condition |
  Non-Clinical Phenotype |
  Disease |
  Treatment / Exposure / Perturbation |
  Metabolite |
  Chemical / Cofactor / Ligand |
  Biological Process / Function |
  Regulatory / Signaling Mechanism / Metabolic Pathway |
  Computational / Model / Algorithm / Data / Metric |
  Method / Assay / Experimental Setup / Parameter / Sample |
  Ecological / Soil / Aquatic / Climate Context |
  Epidemiological / Population |
  Equipment / Device / Material / Instrument |
  Social / Economic / Policy / Management |
  Knowledge / Concept / Hypothesis / Theoretical Construct |
  Property / Measurement / Characterization |
  Others: <custom label>

**RELATIONSHIP_LABELS** — used ONLY in relationship_label:
  [Activation / Induction / Causation / Result] |
  [Repression / Inhibition / Negative Regulation] |
  [Regulation / Control] |
  [Expression / Detection / Identification] |
  [Association / Interaction / Binding] |
  [Localization / Containment / Composition] |
  [Requirement / Activity / Function / Participation] |
  [Encodes / Contains] |
  [Lacks / Dissimilar] |
  [Synthesis / Formation] |
  [Modification / Changes / Alters] |
  [Treatment / Exposure / Perturbation / Administration] |
  [Comparison / Evaluation / Benchmarking] |
  [Definition / Classification / Naming] |
  [Property / Characterization] |
  [Hypothesis / Assumption / Proposal] |
  [Temporal / Sequential Relationship] |
  [Is / Similarity / Equivalence / Analogy] |
  [Limitation / Innovation / Improvement / Advancement] |
  [No Effect / Null Relationship] |
  [Others: <custom label>]

---

### DEFINITION RULES ###

1) **Extracted definition (preferred)**  
   - If the text defines/describes the entity, write a ≤22-word simplified definition grounded in the paper’s wording.
   - Always expand abbreviations where long-form + short-form appear (e.g., “Cellulose synthase 1 (CESA1)”).  
   - Example:  
     Input: “Cellulose synthase 1 (CESA1) is the enzyme that synthesizes cellulose.”  
     Output: `"Cellulose synthase 1 (CESA1) is an enzyme that synthesizes cellulose for plant cell walls."`

2) **Generated definition (fallback)**  
   - Only if extracted definition = "NA".
   - Produce a neutral, domain-safe definition in ≤22 words.  
   - Must not introduce **new**, highly specific functions, roles, or mechanisms that are not broadly recognized general facts about that entity type.  
   - Avoid narrow mechanistic claims; keep wording general and conservative.  
   - Example:
      Input: (no definition in text for “Cellulose synthase 6 (CESA6)”)
      Output: "Cellulose synthase 6 (CESA6) is a plant cellulose synthase protein involved in building cellulose in cell walls."

3) **Abbreviation handling (names and definitions)**  
   - When both long-form and short-form appear in the text (or in a glossary), always write entity names in the canonical form:  
     `<Long Form> (Short Form)` in:
      • source  
      • target  
      • source_extracted_definition  
      • target_extracted_definition
      
4) **Mutual exclusivity (HARD)**
   - For each node: exactly one of {extracted_definition, generated_definition} is non-"NA".
   - If extracted_definition != "NA" → generated_definition MUST be "NA".
   - If extracted_definition = "NA" → generated_definition MUST be filled, unless entity type is too unclear (then "NA" allowed).

5) **Type Naming Constraint (No Invented Long Forms)**  
   - source_type/target_type must be based only on explicit subtype descriptions in the input text.  
   - Do NOT create long-form names that are not present anywhere in the text or its glossary.  
   - Do NOT derive long-forms or species names from prefixes, naming patterns, or external knowledge.  
   - If subtype absent, use a generic type (e.g., protein/gene/enzyme).

---

### SPECIES AND BASIS RULES ###

1) **Species (text-derived only)**  
   - Include only organisms explicitly mentioned in the paper (either as a scientific name or a common name like “mouse”, “rat”, “human”, etc.).  
   - Always output scientific names; unambiguous common names may be normalized (e.g., mouse → Mus musculus).
   - If multiple, separate with semicolons; if none mentioned, output "NA".
   - Never infer species from gene names.

2) **Basis (text-derived only)**  
   - List only experimental methods, analyses, or techniques explicitly mentioned in the text.  
   - Example: “RNA-seq”, “mutant phenotype analysis”, “co-IP”, “confocal microscopy”.  
   - Do not infer methods; if absent, output “NA”.

3) **If basis is unclear**
- If the text does not clearly state supporting methods for a relationship, set `basis` = "NA".

---

### EXPERIMENTAL CONTEXT RULES ###

1）Extract experimental context by interpreting the experimental evidence in the text (method-based inference is allowed).
   - ALLOWED_EXPERIMENTAL_CONTEXTS:
      - in vivo::human_cohort (Homo sapiens)
      - in vivo::human_intervention (Homo sapiens)
      - in vivo::mouse_model (Mus musculus)
      - in vivo::other_animal_model (ORGANISM_SCIENTIFIC_NAME)
      - ex vivo (ORGANISM_SCIENTIFIC_NAME)
      - in vitro
      - in situ
      - in silico
      - NA

2）Context may be inferred from methods.
   - bioinformatics, statistical modeling, simulations → in silico
   - Pure culture, bacterial isolate experiments or bacterial growth assays → in vitro
   - RNA-seq, mutant analysis, cell culture, etc. may be used to infer context if standard usage is clear.
   - Human cohort keywords (e.g., cohort, case-control, cross-sectional, longitudinal, registry, observational) → in vivo::human_cohort
   - Human intervention keywords (e.g., randomized trial, clinical trial, supplementation, drug treatment, vaccine, fecal transplant, dietary intervention) → in vivo::human_intervention
   - Mouse model keywords (e.g., mice, murine, gnotobiotic mice, germ-free mice) → in vivo::mouse_model
   - Other animal keywords (e.g., pig, zebrafish, chicken, Drosophila, C. elegans, nonhuman primate) → in vivo::other_animal_model

3) Multiple contexts:
   - Never use "mixed".
   - If multiple apply, separate with semicolons.
      - Example: in vivo::human_cohort (Homo sapiens); in silico

4) In vivo / ex vivo organism annotation:
   - Whole organism → in vivo::<subtype> (SCIENTIFIC_NAME)
   - Tissues/biopsies/explants/organoids/primary cells → ex vivo (SCIENTIFIC_NAME).
   - The organism must be explicitly mentioned in the text
   - Parentheses must contain the scientific name (not common names).
   - If experimental_context uses in vivo::…(...) or ex vivo(...), `species` MUST include the same scientific name.
   - If context is clearly in vivo/ex vivo but organism is not mentioned → experimental_context = "NA".

5) If no experimental or computational context can be determined → "NA"

---

### ASSOCIATED PROCESS / PATHWAY RULES ###

Applies only to:
- extracted_associated_biological_pathway_or_mechanism
- generated_associated_biological_pathway_or_mechanism
These are triplet-level metadata only; do NOT use them to decide entity categories.

1) **Eligibility Gate (HARD — prevents wrong EXTRACTED values)**
   - extracted_associated_biological_pathway_or_mechanism MUST be "NA" unless the text contains an explicit pathway/mechanism label, such as:
      - contains: “pathway”, “signaling”, “cascade”, “axis”, “system”, “response”, “biosynthesis”, “metabolism”, “differentiation”
      - OR is a universally recognized standalone pathway name (e.g., “glycolysis”, “TCA cycle”, “urea cycle”, “oxidative phosphorylation”).
   - Do NOT treat behaviours, exposures, conditions, or clinical outcomes as pathways/mechanisms.

2) **Extracted (VERBATIM-STRICT)**
   - Output a value only if the authors explicitly name a pathway/mechanism/process using established scientific terminology.
   - Copy the author’s wording exactly as written (case, hyphens, Greek letters, pathway name), with only trivial normalization allowed:
   - Only trivial cleanup allowed (whitespace/hyphen variants/trailing punctuation).
   - No paraphrasing, synonym swaps, acronym expansion, or “standardization”.
   - If the text only describes a process without naming it (e.g., “increased inflammatory markers”, “enhanced lipid breakdown”), output NA.
      ✅ Valid (EXTRACTED): exact strings like “NF-κB signaling pathway”, “Th17 cell differentiation”, “glycolysis”, “Toll-like receptor signaling pathway”.
      ❌ Invalid (EXTRACTED): paraphrases like “NF-kB pathway activation” if no explicit mention in text; summaries like “intestinal inflammation measurement”.

3) **Generated (fallback, optional)**
   - Only if extracted = "NA".
   - Generate ONE short, broad, widely used canonical label linked to the triplet; do not add new claims.
   - If you cannot generate a term that is widely recognized (i.e., you’d be inventing a name, being narrative, or speculating), output NA.
      ✅ Valid (GENERATED): “inflammatory signaling”, “lipid metabolism”, “immune response”, “bacterial adhesion”.
      ❌ Invalid (GENERATED): “microbiome-driven neurological rewiring”, “complex host–microbial interaction dynamics”.

4) Mutual exclusivity (HARD)
   - If extracted != "NA" → generated MUST be "NA".
   - If extracted = "NA" → generated may be a label or "NA" (prefer "NA" over invented terms).

---

### RELATIONSHIP AND NODE RULES ###

1) **Atomicity of nodes (HARD)**  
   - Nodes represent the smallest meaningful biological entity or concept.
   - Nodes must NOT contain effect/modifier wrappers. These wrappers MUST be moved into the relationship.
   - Descriptors like “activity”, “expression”, “accumulation”, “level”, “content”, "inhibition" etc. belong in the **relationship**, not the node.
      ✅ Valid examples: "pentose phosphate pathway" + "activation increases" + "DNA synthesis"
      ❌ Invalid example: "activation of pentose phosphate pathway" as source

2) **Relationship field (HARD)**  
   - Relationship phrases must use active, biologically interpretable verbs.  
   - If a process + verb are both stated, combine them (e.g., “overexpression decreases expression of”, “binding enhances”).  
   - Avoid passive constructions, rewrite as active (“is activated by” → activates”).

3) **Atomic Decomposition Rule (HARD)**  
   - For every mechanistic chain with multiple sequential causal events, create one binary relationship per explicit causal verb, even when multiple effects appear in one sentence.  
   - Example:
      "Gibberellin A₄ (GA₄) increases ELONGATED HYPOCOTYL 5 (HY5), and HY5 represses auxin signaling, which inhibits lateral root growth."
      Extract as:
      1. Gibberellin A₄ (GA₄) → increases → ELONGATED HYPOCOTYL 5 (HY5)
      2. ELONGATED HYPOCOTYL 5 (HY5) → represses → auxin signaling
      3. auxin signaling → inhibits → lateral root growth
   - Do not merge multi-step causal chains into a single edge.
   - **Text-grounding constraint for atomic splitting (non-negotiable):**
     - You may split a statement with multiple targets/effects into multiple atomic relationships **only if** the text clearly asserts each pairwise relationship.
     - If the sentence is ambiguous about whether the relation applies to each target individually, **do not split**; instead either:
       (a) extract fewer, higher-confidence edges, or
       (b) skip the ambiguous edges entirely.
     - Example:
       Original:
       “CpPDS2/4 expression correlates with CpZDS, CpLCY-e, CpCHY-b expression and carotenoid content.”
       Split only if the text clearly indicates correlation with each item:
       - CpPDS2/4 expression – correlates with – CpZDS expression  
       - CpPDS2/4 expression – correlates with – CpLCY-e expression  
       - CpPDS2/4 expression – correlates with – CpCHY-b expression  
       - CpPDS2/4 expression – correlates with – carotenoid content  
     - Do NOT create atomic triples whose support by the text is ambiguous.

4) **Explicitness Rule (No Indirect Implied Edges)**  
   - Only extract relationships that are explicitly stated by the text using causal, regulatory, mechanistic, or descriptive verbs.  
   - Do NOT create edges that are implied but not explicitly stated.  
   - Example:
      "HY5 represses auxin signaling, which inhibits lateral root growth."
      ✅ Extract:
      - ELONGATED HYPOCOTYL 5 (HY5) → represses → auxin signaling
      - auxin signaling → inhibits → lateral root growth
      ❌ Do NOT extract:
      - ELONGATED HYPOCOTYL 5 (HY5) → inhibits → lateral root growth

5) **Multi-actor rule (AND relationships)**  
   - If A and B are **jointly required** (“A and B together activate C”, “A–B heterodimer activates C”), allow a multi-entity source:  
      • “A and B” → jointly activate → C  
   - If the text does NOT explicitly describe joint action, split into independent edges:  
      • A → activates → C  
      • B → activates → C  

6) **Multi-target rule**  
   - If X is stated to act on multiple targets in the same way (“X activates Y and Z”, “X inhibits Y and Z”), decompose into separate binary relationships:  
      • X → activates → Y  
      • X → activates → Z
   - Apply this only when the text clearly supports the same relationship between the source and each target individually.

7) **Limit multi-entity nodes (HARD)**  
   - Allow at most two entities in a node, only when explicitly necessary (joint requirement, heterodimers, complexes).  
   - Otherwise, split into multiple relationships.

8) **Canonical combined naming rule for source and target (long-form + short-form) (HARD)**  
   - When both a long-form and short-form for the same entity appear anywhere in the text **or in a glossary**, you MUST rewrite the entity name into the combined canonical form:
      <Long Form> (Short Form)
   - Example (only if both forms appear in the document or glossary):
      "ELONGATED HYPOCOTYL 5" + "HY5" → "ELONGATED HYPOCOTYL 5 (HY5)"
   - This canonical combined form must be used consistently for:
      • source
      • target
      • source_extracted_definition
      • target_extracted_definition
   - If ONLY the short-form appears and no long-form appears anywhere in the text or glossary, keep the entity as the short-form symbol (e.g., "HY5").  
   - If ONLY the long-form appears and no short-form appears anywhere, keep the entity as the long-form string exactly as written.
   - Do NOT invent long-forms that are not present in the text or its glossary.
   - These functional descriptors (protein, enzyme, kinase, transcription factor, receptor, etc.) belong in `source_type` or `target_type`, not in the entity name.

9) **Hedging and modality preservation (HARD)**  
   - Preserve hedging/modality from the text instead of converting uncertain statements into definite factual triples.  
   - When the text uses terms like “believed to”, “assumed to”, “suggested to”, “proposed to”, “may”, “might”, “could”, “likely”, “thought to”, “hypothesized”:
      - Reflect this uncertainty in the `relationship` phrase (e.g., “may promote”, “is suggested to repress”, “is hypothesized to interact with”), and/or  
      - If the statement is hedged/speculative, `relationship_label` MUST be "[Hypothesis / Assumption / Proposal]", overriding any other label that might otherwise fit.
   - Do NOT upgrade speculative/correlational statements to definite causal claims.

10) **Classification, descriptive, temporal, and compositional relationships (HARD)**
   - You MUST extract definitional/descriptive relations, not only causal ones.
   - Always extract these constructions when explicitly stated:
      "X is a Y" | "X is" | "X belongs to Y" | "X is part of Y" | "X contains Y" |
      "X is located in Y" | "X occurs during Y" | "X is essential for Y" |
      "X is one of Y" | "X is allelic to Y" | "X is used as Y"
   - Do NOT skip these as “background” facts.
   - Examples:
      ✅ "ABA" → "is" → "stress hormone"
      ✅ "Oryza sativa" → "is used as model for" → "cereal crop genetics"
      ✅ "stomatal closure" → "occurs during" → "drought stress"
      ✅ "chloroplast" → "contains" → "thylakoid membranes"
      ✅ "AtMYB12" → "is one of" → "R2R3-MYB transcription factors"

11) **Comprehensiveness (HARD)**
   - Process EVERY sentence in the text.
   - Extract EVERY explicitly stated biological relationship from EVERY sentence (not only the main findings).
   - Relationships involving general biological facts, organism descriptions, method descriptions, and experimental observations are all valid for extraction if explicitly stated.
---

### RELATIONSHIP LABEL RULES ###


1) **Exact bracketed output (HARD)**
   - `relationship_label` MUST contain exactly one value from RELATIONSHIP_LABELS.
   - The value MUST be returned exactly as written, including the surrounding square brackets.
   - Do NOT omit the brackets.
   - Do NOT add any extra words, punctuation, explanation, or qualifiers.
   - Valid examples:
      [Regulation / Control]
   - Invalid examples: Regulation / Control, [Regulation]
   
2) Grouped-label interpretation:
   - Relationship labels are slash-separated grouped labels.
   - A relationship does not need to match every term in the label.
   - Assign the label if it best matches one or more components of that grouped label.

3) **Avoid “Others:” unless absolutely no predefined label applies.**  
   - If the relationship can logically fit *any* listed label, do **not** assign “Others”.

4) **Ambiguous or domain-specific terms must be mapped to the closest predefined label.**  
   Examples:  
   - “genetic epistasis” → [Regulation / Control]  
   - “gene–gene interaction” → [Association / Interaction / Binding] 
   - “methodological use” → [Expression / Detection / Identification]
   - “functional requirement” → [Requirement / Activity / Function / Participation]
   - “functional dependency” → [Regulation / Control]
   - “experimentally tested relationship” → [Expression / Detection / Identification]

5) **If a relationship fits multiple labels, choose the most general one.**  
   - “affects”, “modulates”, “influences” → [Regulation / Control]
   - “binds”, “associates”, “interacts” → [Association / Interaction / Binding]
   - “detects”, “measures”, “quantifies” → [Expression / Detection / Identification]
   - “forms”, “produces”, “synthesizes” → [Synthesis / Formation]

6) **Never invent custom sublabels inside “[Others:<custom label>]” for standard biological terms.**  
   - Do not output labels like “[Others: epistasis]” or “[Others: methodological use]”.  
   - Only use “[Others:<custom label>]” for concepts genuinely outside all categories (e.g., “cultural factor”).

---

### ENTITY CATEGORY SELECTION RULES ###

1) General Principles
- Choose the most specific category from ENTITY_CATEGORIES only; never use any value from RELATIONSHIP_LABELS as an entity category.
- Do NOT collapse specific entities into broader ones.
- Use `Others:<custom label>` only if no predefined category fits.
- **Grouped-label interpretation:** 
   - Entity categories are slash-separated grouped labels.
   - An entity does not need to satisfy every term in the label.
   - Choose the single category whose label components provide the closest overall fit.
- **Head-term anchoring:** categorize by what the head-term *is*; modifiers (inflammatory/gut/altered/etc.) must not override.
- **Example-pattern generalization:** apply valid/invalid example patterns to similarly constructed phrases.
   ❌ “butyrate-producing bacteria” (functional descriptor) → any similarly formed “X-producing bacteria” phrase is NOT Microbial Species.

2) Category Definitions

**Core Molecular & Genetic Entities**

- Gene / Protein
   - Individual genes, proteins, enzymes, transcription factors, kinases, receptors.
   - Broad protein types/classes also belong here.  
   - Valid: IL6, TNF-α,  TLR4, tryptophan decarboxylase, cytokines, growth factors, enzymes
- Genomic / Transcriptomic / Proteomic / Epigenomic Feature / Gene Mutant
   - Omics-level features, mutations, engineered expression states.
   - Valid: SNP variant, knockout mutant, overexpression line, methylation mark, 16S rRNA gene

**Microbial & Taxonomic**

- Microbial Species
   - Explicitly named species-level microbial taxa.
   - Valid: Enterocloster bolteae, Bacteroides fragilis, Escherichia coli
   - Invalid: gut microbiome, commensal bacteria, butyrate-producing bacteria, acid-tolerant bacteria, pathogens
- Virus
  - Explicitly named viral entities.
  - Valid: SARS-CoV-2, Epstein–Barr virus, bacteriophage T4
  - Invalid: viral infection, viral vector, phage genes
- Taxonomic / Evolutionary / Phylogenetic Group
   - Higher-level organism classifications (family, genus, phylum, class, kingdom).
   - Valid: Firmicutes, Bacteroidetes, Enterobacteriaceae, Proteobacteria, mammals
   - Invalid: pathogenic bacterial drivers, multiple bacterial species, commensal bacteria
- Complex / Structure / Compartment / Cell / Organ / Organism
   - Generic biological entities, components or anatomical contexts + general microbial community references.
   - Valid: gut microbiota, gut bacteria, oral bacteria, intestinal bacteria, colon, immune cells
   - Invalid: healthy volunteers/controls, in-vivo models, clinical cohort

**Clinical & Phenotypic**

- Clinical Phenotype / Clinical Trait / Host Condition
   - host physiological/lifestyle/pathological states.
   - **human-first** unless explicitly an experimental condition.  
   - Valid: ileal inflammation, gut microbiota dysbiosis, long-term physiological stress, obesity, high-fat diet, alcohol consumption
- Non-Clinical Phenotype
   - Microbial/cellular/organism traits not framed as host clinical state.
   - Valid: biofilm formation, motility, antibiotic resistance, virulence, colonization ability, growth rate
- Disease
   - Named pathological disorders and diseases.
   - Valid: Crohn’s disease, colorectal cancer, ulcerative colitis, diabetes
- Treatment / Exposure / Perturbation
   - Administered treatments, compounds, interventions, exposure, stressors, or applied physical/chemical conditions used to modify the state of a system.
   - Includes clinical therapies, drugs, dietary interventions, microbial transplants, environmental exposures, and experimental perturbations.
   - Valid: metformin, antibiotics, fecal microbiota transplantation, probiotic supplementation, dietary therapy, butyrate supplementation, heat, UV, osmotic stress
   - Invalid: obesity, gut microbiota dysbiosis (these are Clinical Phenotype / Host Condition); ecological descriptions (under Ecological Context)

**Metabolic & Chemical**

- Metabolite
   - Biological metabolic substrates, intermediates, or end-products.
   - Valid: butyrate, acetate, propionate, indole, secondary bile acids, short-chain fatty acids
- Chemical / Cofactor / Ligand
   - Functional molecule not primarily defined as a metabolic product.
   - Includes cofactors, structural molecules, ions, synthetic compounds, macromolecules.
   - Valid: ATP, NAD+, lipopolysaccharide, polysaccharides, calcium ions

**Process & Mechanism**

- Biological Process / Function
   - Broad or generic biological processes and activity.
   - Valid: inflammation, immune response, metabolism, microbial colonization, decarboxylation, oxidative stress
   - Invalid: Genes, proteins, tryptophan decarboxylase, IL-33 signaling, pentose phosphate pathway
- Regulatory / Signaling Mechanism / Metabolic Pathway
   - Named pathways/cascades or metabolic pathways.
   - Valid: NF-κB signaling pathway, MAPK cascade, short-chain fatty acid biosynthesis pathway, bile acid metabolism pathway, quorum sensing
   - Invalid: broad processes, inflammation, tryptophan decarboxylase

**Computational & Supporting**

- Computational / Model / Algorithm / Data / Metric
   - Valid: random forest, GNN model, metagenomic dataset, Shannon diversity index, ROC-AUC
- Method / Assay / Experimental Setup / Parameter / Sample
   - Valid: 16S rRNA sequencing, qPCR, stool sample, germ-free mouse model
- Ecological / Soil / Aquatic / Climate Context
   - Valid: soil microbiome, marine environment, aquatic habitat, temperature
- Epidemiological / Population
   - Valid: clinical cohort, pediatric cohort, elderly population, case-control group
- Equipment / Device / Material / Instrument
   - Valid: Illumina sequencer, mass spectrometer, anaerobic chamber
- Social / Economic / Policy / Management
   - Valid: antibiotic stewardship policy, healthcare access
- Knowledge / Concept / Hypothesis / Theoretical Construct
   - Valid: hygiene hypothesis, gut–brain axis concept
- Property / Measurement / Characterization
   - Valid: microbial abundance, alpha diversity, binding affinity, enzyme activity
- Others: <custom label>
   - Use sparingly.
   - Keep label concise (≤3 words).

3) Cross-Category Resolution Rules

Microbial Specificity
- Specific scientific name → Microbial Species.
- Higher-level classification (family/phylum/class/etc.) → Taxonomic / Evolutionary / Phylogenetic Group.
- Generic phrases like “gut bacteria”, “microbial community” → Complex / Structure / Compartment / Cell / Organ / Organism.
- General terms like “bacteria” NEVER belong under Taxonomic / Evolutionary / Phylogenetic Group.

Clinical vs Phenotype
- Named disorder → Disease.
- Host measurable or physiological state (human bias) → Clinical Phenotype / Clinical Trait / Host Condition.
- Microbial or cellular trait → Non-Clinical Phenotype.

Metabolite vs Chemical
- Product of biological metabolism → Metabolite.
- Structural molecule, ion, cofactor, ligand, or synthetic compound → Chemical / Cofactor / Ligand.

Process vs Pathway
- General term (e.g., “metabolism”, “inflammation”) → Biological Process / Function.
- Specific named pathway (e.g., “NF-κB signaling”, “butyrate metabolism”) → Regulatory / Signaling Mechanism / Metabolic Pathway.


4) Canonical Naming Rule for Gene / Protein Entities

- If both long-form and short-form appear in the text or glossary, use:
  <Long Form> (Short Form)
- If only the short-form appears, keep the short-form (e.g., "HY5").
- If only the long-form appears, keep the long-form string.
- Do NOT invent long-forms that are not present in the text.
- Functional descriptors (protein, enzyme, kinase, receptor, etc.) belong in source_type / target_type, not in the entity name.

---

### IDENTIFIER EXTRACTION RULES (STRICT SYMBOL VALIDATION — NO INFERENCE - NON-NEGOTIABLE) ###

IDENTIFIER EXTRACTION MASTER OVERRIDE RULE:
The model MUST first classify the entity's category. 
Only after classification is done may the model evaluate symbols.

If source_category != "Gene / Protein", then source_identifier MUST be "NA" without exception.
If target_category != "Gene / Protein", then target_identifier MUST be "NA" without exception.

This applies especially to:
- Genomic / Transcriptomic / Proteomic / Epigenomic Feature / Gene Mutant
- Treatment / Exposure / Perturbation
- Biological Process / Function
- Metabolite
- Chemical / Cofactor / Ligand

In these categories, you MUST NEVER output any non-"NA" identifier, even if the name contains tokens like "CHLI-A", "TaBG1", "GA20ox2", or other gene-like patterns.

If category = "Gene / Protein":
   identifier must match exactly the explicit short-form symbol or locus ID present in the text.
   UNLESS the entity is a protein family / protein class / protein group / domain / variant / construct / multi-protein assembly / overexpression line / mutant line, in which case identifier MUST be "NA".

Pattern-like strings, protein families, classes, variants, overexpression lines, mutant lines, constructs, domains, or multi-protein assemblies DO NOT receive identifiers, even if they contain symbol-like strings.

------------------------------------------------------------
A. Eligibility (Category-First Enforcement)
------------------------------------------------------------

1. The model MUST determine the entity’s category first.  
2. Identifiers may be assigned ONLY IF:
   - `source_category == "Gene / Protein"` or `target_category == "Gene / Protein"`.  
3. If the entity belongs to ANY other category:
   - identifier = "NA"
   even if the name looks like a symbol, contains digits, capital letters, resembles a gene family, or appears in parentheses.  
4. Pattern detection MUST NOT cause a non-gene entity to be treated as a gene.

Examples:
- JA (hormone) → category Chemical / Cofactor / Ligand → identifier = "NA"  
- auxin (hormone) → identifier = "NA"  
- cutin, suberin (polymers) → identifier = "NA"  
- hy5 mutant (mutant) → identifier = "NA"  
- FKF1–CDF2 complex → identifier = "NA"  
- light, cold, blue light → identifier = "NA"  

------------------------------------------------------------
B. What counts as a valid gene/protein symbol?
------------------------------------------------------------

Only evaluate these patterns AFTER confirming category = Gene / Protein.

A token is a valid gene/protein symbol ONLY if it matches ANY of:
1. **Organism-prefixed symbols**  
   - Pattern: `<Prefix><Letters><Digits><optional lowercase/letter suffix>`  
   - Examples: AtWRKY43, ZmFKF1a, OsMADS47, MpCYP1  
2. **Uppercase letter–digit symbols (2–8 uppercase letters + digits)**  
   - Examples: CBF3, FT1, WRKY33, MPK3  
3. **Mixed letter–digit enzyme-like symbols**  
   - Examples: LOX2, LTPG16, PAL1, MYB46 
4. **Hyphenated symbols**  
   - Examples: CHLI-A, WRKY33-B  
5. **Locus-like identifiers**  
   - Examples: AT3G18790, TraesCS7A02G480700, Solyc05g012345  
6. **Parenthesized symbols**  
   - If `(X)` contains a valid symbol by the rules above, X is extracted as a symbol.  
7. **Multi-symbol constructs**  
   - When tokens include commas, “and”, or “&”, split and validate each part independently.  

------------------------------------------------------------
C. Identifier Assignment Priority (only if Gene / Protein)
------------------------------------------------------------

Once category = Gene / Protein AND a valid symbol pattern exists, apply:

1. **Explicit author-defined symbols or locus identifiers stated in the text override all heuristics**
2. **Explicit locus IDs**  
   - If a locus ID appears (e.g., AT3G25690), identifier = locus ID exactly.  
3. **Long-form + Short-form pattern**  
   - If the entity appears as `<Long Form> (Short Form)` and the Short Form is a valid symbol:  
      - identifier = `<Short Form>` only.  
4. **Dual symbol A (B)**  
   - If both A and B are valid symbols: identifier = `"A , B"`.  
5. **Multiple symbols A, B and C**  
   - identifier = `"A | B | C"`.  
6. **Canonical symbol alone**  
   - If only a symbol (e.g., "AtLTPG16") appears: identifier = that symbol.  
7. **Long-form only (no symbol)**  
   - If only a long-form gene/protein name appears and no short-form symbol is present anywhere:  
      - identifier = that long-form string exactly as written.  
8. **Short-form only**  
   - If only a short-form symbol appears and the text explicitly calls it a gene/protein:  
      - identifier = that short-form symbol.

If a short-form symbol appears but pattern detection is uncertain:
- If the text explicitly states that this entity is a “gene” or “protein”, the short-form MUST still be used as the identifier.

------------------------------------------------------------
D. Entities that MUST always have identifier = "NA"
------------------------------------------------------------

(Regardless of symbol patterns or appearance, because category != Gene / Protein)

- metabolites (tryptophan, secologanin, GA3, IAA)  
- hormones (ABA, JA, auxin, cytokinin)  
- pathways, processes, signaling systems (auxin signaling)  
- chemical intermediates, alkaloids  
- gene families (DELLAs, PIFs, F-box family)  
- mutants, alleles, genotypes (hy5 mutant, LOX2 KO) 
- overexpression / knockout lines (35S::FKF1, ZmGI1-OE)  
- protein complexes not representing a single gene product  
- environmental/treatment conditions (blue light, cold, drought)  
- ChEBI compounds  

------------------------------------------------------------
E. Correct examples
------------------------------------------------------------

1. MpCYP1 (MpSOS)  
   - Category: Gene / Protein  
   - Identifier: `"MpCYP1 , MpSOS"`  
2. MpAO and MpDAR  
   - Category: Gene / Protein  
   - Identifier: `"MpAO | MpDAR"`  
3. Glycerol-3-phosphate acyltransferase 5 (AtGPAT5)  
   - Category: Gene / Protein  
   - Identifier: `"AtGPAT5"`  
4. AtLTPG16
   - Category: Gene / Protein
   - Identifier: `"AtLTPG16"`
5. JA  
   - Category: Chemical / Cofactor / Ligand
   - Identifier: `"NA"`  
6. auxin signaling  
   - Category: Regulatory / Signaling Mechanism / Metabolic Pathway
   - Identifier: `"NA"`  
7. hy5 mutant  
   - Category: Genomic / Transcriptomic / Proteomic / Epigenomic Feature / Gene Mutant
   - Identifier: `"NA"`  
8. Protein families, gene families, domains, motifs, variants, isoforms, truncated constructs, and splice variants
   - Category = Genomic / Transcriptomic / Proteomic / Epigenomic Feature / Gene Mutant
   - Identifier = "NA"   
9. "ectopic expression of TaBG1"
   - Category: Genomic / Transcriptomic / Proteomic / Epigenomic Feature / Gene Mutant
   - Identifier: "NA"
10. "CHLI-A expression"
   - Category: Property / Measurement / Characterization
   - Identifier: "NA"

---

### COREFERENCE RESOLUTION ###
Resolve references like “this pathway”, “these effects”, “this gene” to the nearest explicit antecedent **within the same section only**.  
If none exists, ignore the coreference.

---

### OUTPUT CONSTRAINTS ###
- Return **only valid JSON** (no markdown, explanations, or comments).  
- Do not include citations or external references.

---

### ✅ EXAMPLES ###
**Input text:**  
Sodium butyrate (NaB) treatment reduced Toll-like receptor 4 (TLR4) expression in the colon of Parkinson’s disease (PD) model mice. 
Western blot and qPCR showed reduced activation of the NF-κB signaling pathway and decreased colonic inflammation after NaB treatment. 
16S rRNA sequencing revealed increased abundance of Lactobacillus in fecal samples from NaB-treated mice. 
NF-κB signaling pathway activation promotes inflammatory cytokines.

**Output:** 
[
  {
    "source": "Sodium butyrate (NaB)",
    "source_identifier": "NA",
    "source_type": "short-chain fatty acid",
    "source_category": "Metabolite",
    "source_extracted_definition": "NA",
    "source_generated_definition": "Sodium butyrate (NaB) is a short-chain fatty acid often used to modulate host and microbial responses.",

    "relationship": "treatment reduces expression of",
    "relationship_label": "[Treatment / Exposure / Perturbation / Administration]",

    "target": "Toll-like receptor 4 (TLR4)",
    "target_identifier": "TLR4",
    "target_type": "pattern recognition receptor",
    "target_category": "Gene / Protein",
    "target_extracted_definition": "Toll-like receptor 4 (TLR4) expression was reduced in the colon after NaB treatment.",
    "target_generated_definition": "NA",

    "species": "Mus musculus",
    "basis": "qPCR; Western blot",
    "experimental_context": "in vivo::mouse_model (Mus musculus)",

    "extracted_associated_biological_pathway_or_mechanism": "NF-κB signaling pathway",
    "generated_associated_biological_pathway_or_mechanism": "NA"
  },
  {
    "source": "Sodium butyrate (NaB)",
    "source_identifier": "NA",
    "source_type": "short-chain fatty acid",
    "source_category": "Metabolite",
    "source_extracted_definition": "NA",
    "source_generated_definition": "Sodium butyrate (NaB) is a short-chain fatty acid often used to modulate host and microbial responses.",

    "relationship": "treatment reduces activation of",
    "relationship_label": "[Treatment / Exposure / Perturbation / Administration]",

    "target": "NF-κB signaling pathway",
    "target_identifier": "NA",
    "target_type": "inflammatory signaling pathway",
    "target_category": "Regulatory / Signaling Mechanism / Metabolic Pathway",
    "target_extracted_definition": "Activation of the NF-κB signaling pathway was reduced after NaB treatment.",
    "target_generated_definition": "NA",

    "species": "Mus musculus",
    "basis": "Western blot",
    "experimental_context": "in vivo::mouse_model (Mus musculus)",

    "extracted_associated_biological_pathway_or_mechanism": "NF-κB signaling pathway",
    "generated_associated_biological_pathway_or_mechanism": "NA"
  },
  {
    "source": "Sodium butyrate (NaB)",
    "source_identifier": "NA",
    "source_type": "short-chain fatty acid",
    "source_category": "Metabolite",
    "source_extracted_definition": "NA",
    "source_generated_definition": "Sodium butyrate (NaB) is a short-chain fatty acid often used to modulate host and microbial responses.",

    "relationship": "treatment decreases",
    "relationship_label": "[Treatment / Exposure / Perturbation / Administration]",

    "target": "colonic inflammation",
    "target_identifier": "NA",
    "target_type": "host inflammatory state",
    "target_category": "Clinical Phenotype / Clinical Trait / Host Condition",
    "target_extracted_definition": "Colonic inflammation decreased after NaB treatment.",
    "target_generated_definition": "NA",

    "species": "Mus musculus",
    "basis": "NA",
    "experimental_context": "in vivo::mouse_model (Mus musculus)",

    "extracted_associated_biological_pathway_or_mechanism": "NA",
    "generated_associated_biological_pathway_or_mechanism": "inflammatory signaling"
  },
  {
    "source": "16S rRNA sequencing",
    "source_identifier": "NA",
    "source_type": "microbiome profiling method",
    "source_category": "Method / Assay / Experimental Setup / Parameter / Sample",
    "source_extracted_definition": "16S rRNA sequencing was used to profile fecal microbial composition.",
    "source_generated_definition": "NA",

    "relationship": "reveals increased abundance of",
    "relationship_label": "[Expression / Detection / Identification]",

    "target": "Lactobacillus",
    "target_identifier": "NA",
    "target_type": "bacterial genus",
    "target_category": "Taxonomic / Evolutionary / Phylogenetic Group",
    "target_extracted_definition": "16S rRNA sequencing revealed increased Lactobacillus abundance in fecal samples from NaB-treated mice.",
    "target_generated_definition": "NA",

    "species": "Mus musculus",
    "basis": "16S rRNA sequencing",
    "experimental_context": "in vivo::mouse_model (Mus musculus)",

    "extracted_associated_biological_pathway_or_mechanism": "NA",
    "generated_associated_biological_pathway_or_mechanism": "NA"
  }
]

**Mini-Example 2 (diverse relationship labels):**
**Input text:**
Butyrate is a short-chain fatty acid produced by gut bacteria. Faecalibacterium prausnitzii is a major butyrate-producing bacterium in the human gut microbiota.
Reduced abundance of Faecalibacterium prausnitzii is associated with Crohn’s disease. 16S rRNA sequencing was used to characterize microbial community composition.
Short-chain fatty acid production occurs during microbial fermentation of dietary fiber. Butyrate inhibits activation of the NF-κB signaling pathway in colonic epithelial cells.
The human gut microbiota contains Firmicutes and Bacteroidetes.

**Output (source/relationship/target only):**
[
  {"source": "butyrate", "relationship": "is", "target": "short-chain fatty acid"},
  {"source": "gut bacteria", "relationship": "produce", "target": "short-chain fatty acid"},
  {"source": "Faecalibacterium prausnitzii", "relationship": "is", "target": "major butyrate-producing bacterium"},
  {"source": "Faecalibacterium prausnitzii", "relationship": "reduced abundance is associated with", "target": "Crohn’s disease"},
  {"source": "16S rRNA sequencing", "relationship": "characterizes", "target": "microbial community composition"},
  {"source": "short-chain fatty acid", "relationship": "production occurs during", "target": "microbial fermentation"},
  {"source": "microbial fermentation", "relationship": "acts on", "target": "dietary fiber"},
  {"source": "butyrate", "relationship": "inhibits activation of", "target": "NF-κB signaling pathway"},
  {"source": "NF-κB signaling pathway", "relationship": "is in", "target": "colonic epithelial cells"},
  {"source": "human gut microbiota", "relationship": "contains", "target": "Firmicutes"},
  {"source": "human gut microbiota", "relationship": "contains", "target": "Bacteroidetes"}
]

Note how Mini-Example 2 demonstrates:
- Classification relationship ("is" → short-chain fatty acid; major butyrate-producing bacterium)
- Compositional relationship ("contains" → Firmicutes; Bacteroidetes) — also shows multi-target decomposition into separate triples
- Modifier embedded in relationship phrase ("reduced abundance is associated with" → Crohn's disease)
- Method-based relationship ("16S rRNA sequencing" → "characterizes")
- Temporal relationship ("production occurs during" → microbial fermentation)
- Inhibition with nested process ("inhibits activation of" → NF-κB signaling pathway)

All of these relationship types are biologically meaningful and must be extracted.

---

**Scientific text:**  
{TEXT}
"""