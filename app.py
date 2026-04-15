from flask import Flask, render_template, request, url_for, redirect, send_from_directory, jsonify, Response, session
import os
import time
from datetime import timedelta
from flask_compress import Compress
import openai
import logging
from pymongo import MongoClient
import json

# Connect to MongoDB
client = MongoClient(os.getenv("MONGO_URI", "mongodb://localhost:27017/"))
db = client["PlantConnectome"]
scientific_chunks = db["scientific_chunks"]

print(f"scientific_chunks collection: {scientific_chunks.count_documents({})} documents")

# Configure logger
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.ERROR, format="%(asctime)s - %(levelname)s - %(message)s")

# Importing Blueprints
from routes.preview_author_search import author_search
from routes.author_search import author_search_results
from routes.title_searches import title_searches
from routes.similarity_search import similarity_search
from routes.catalogue_search import catalogue_search
from routes.api import normal_search, substring_search, api
from routes.term_searches import (
    normal, substring,
    normal_results, normal_results_multi,
    substring_results, substring_results_multi,
)

# Initialize Flask app
app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "plant-connectome-dev-key")

# Production vs development mode
is_production = os.getenv("FLASK_ENV", "development") == "production"

# Session settings
app.config.update(
    SESSION_COOKIE_SECURE=is_production,
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE='Lax',
    PERMANENT_SESSION_LIFETIME=timedelta(hours=1),
)

app.debug = not is_production

Compress(app)

# Register Blueprints
app.register_blueprint(author_search)
app.register_blueprint(author_search_results)
app.register_blueprint(title_searches)
app.register_blueprint(similarity_search)
app.register_blueprint(catalogue_search)
app.register_blueprint(api)

# Register dynamic routes
with app.app_context():
    app.add_url_rule('/normal/<path:query>', 'normal', normal, methods=['GET'])
    app.add_url_rule('/substring/<path:query>', 'substring', substring, methods=['GET'])
    app.add_url_rule('/api/normal/<path:query>', 'api_normal', normal_search, methods=['GET'])
    app.add_url_rule('/api/substring/<path:query>', 'api_substring', substring_search, methods=['GET'])

    app.add_url_rule('/normal/<path:query>/results/<entity_type>', 'normal_results', normal_results, methods=['GET'])
    app.add_url_rule('/substring/<path:query>/results/<entity_type>', 'substring_results', substring_results, methods=['GET'])

    app.add_url_rule('/normal/<path:multi_query>/results', 'normal_results_multi', normal_results_multi, methods=['GET', 'POST'])
    app.add_url_rule('/substring/<path:multi_query>/results', 'substring_multi', substring_results_multi, methods=['GET', 'POST'])


@app.route('/test-session', methods=['GET'])
def test_session():
    if 'test_key' in session:
        test_value = session['test_key']
        return jsonify({'status': 'success', 'message': 'Session is working correctly.', 'test_key': test_value})
    else:
        session['test_key'] = 'Session Initialized'
        return jsonify({'status': 'initialized', 'message': 'Session has been set for the first time.'})


@app.route('/', methods=['GET'])
def index():
    try:
        with open('stats.txt', 'r') as f:
            v = f.read().rstrip().split()
        papers, entities = v[0], v[1]
    except Exception as e:
        logger.error(f"Error reading stats.txt: {str(e)}")
        papers, entities = '0', '0'

    # Preview graph: PSAD1-1 mutant photosynthesis knowledge graph (from PlantConnectome)
    preview = {"nodes": [
        {"data": {"id": "PLHCA4 [PROTEIN]", "type": "protein", "category": "GENE / PROTEIN", "originalId": "pLhca4"}},
        {"data": {"id": "A. THALIANA [ORGANISM]", "type": "organism", "category": "COMPLEX / STRUCTURE / COMPARTMENT / CELL / ORGAN / ORGANISM", "originalId": "A. thaliana"}},
        {"data": {"id": "(PSAD-1, PSAD1, AT4G02770)-1 [GENE IDENTIFIER]", "type": "gene identifier", "category": "GENE / PROTEIN", "originalId": "(PSAD-1, PSAD1, AT4G02770)-1"}},
        {"data": {"id": "130 MOST STRONGLY ATTENUATED GENE(S) [GENE]", "type": "gene", "category": "GENE / PROTEIN", "originalId": "130 most strongly attenuated gene(s)"}},
        {"data": {"id": "OXIDATION OF PHOTOSYSTEM I (PSI) [PHENOTYPE]", "type": "phenotype", "category": "PHENOTYPE / TRAIT / DISEASE", "originalId": "Oxidation of photosystem I (PSI)"}},
        {"data": {"id": "LIGHT-GREEN LEAF COLORATION [PHENOTYPE]", "type": "phenotype", "category": "PHENOTYPE / TRAIT / DISEASE", "originalId": "light-green leaf coloration"}},
        {"data": {"id": "MRNA EXPRESSION OF MOST GENE(S) INVOLVED IN THE LIGHT PHASE OF PHOTOSYNTHESIS [GENE]", "type": "gene", "category": "GENE / PROTEIN", "originalId": "mRNA expression of most gene(s) involved in the light phase of photosynthesis"}},
        {"data": {"id": "PHOSPHORYLATION OF THYLAKOID PROTEIN(S) [TREATMENT]", "type": "treatment", "category": "TREATMENT / PERTURBATION / STRESS / MUTANT", "originalId": "phosphorylation of thylakoid protein(s)"}},
        {"data": {"id": "INCREASED SENSITIVITY TO LIGHT STRESS [PHENOTYPE]", "type": "phenotype", "category": "PHENOTYPE / TRAIT / DISEASE", "originalId": "increased sensitivity to light stress"}},
        {"data": {"id": "PSI AND PSII POLYPEPTIDES [PROTEIN COMPLEX]", "type": "protein complex", "category": "GENE / PROTEIN", "originalId": "PSI and PSII polypeptides"}},
        {"data": {"id": "GROWTH RATE [PHENOTYPE]", "type": "phenotype", "category": "PHENOTYPE / TRAIT / DISEASE", "originalId": "Growth rate"}},
        {"data": {"id": "PSAD MRNA AND PROTEIN(S) [GENE]", "type": "gene", "category": "GENE / PROTEIN", "originalId": "PsaD mRNA and protein(s)"}},
        {"data": {"id": "PQ POOL [METABOLITE]", "type": "metabolite", "category": "CHEMICAL / METABOLITE / COFACTOR / LIGAND", "originalId": "PQ pool"}},
        {"data": {"id": "REDUCTION BY ABOUT 60% OF THE SUBUNITS OF THE STROMAL RIDGE OF PSI [PHENOTYPE]", "type": "phenotype", "category": "PHENOTYPE / TRAIT / DISEASE", "originalId": "reduction by about 60% of the subunits of the stromal ridge of PSI"}},
        {"data": {"id": "PHOTOSYNTHETIC ELECTRON TRANSPORT [PHENOTYPE, PROCESS]", "type": "phenotype, process", "category": "BIOLOGICAL PROCESS / PATHWAY / FUNCTION", "originalId": "Photosynthetic electron transport"}},
    ], "edges": [
        {"data": {"id": "edge0", "source": "(PSAD-1, PSAD1, AT4G02770)-1 [GENE IDENTIFIER]", "target": "REDUCTION BY ABOUT 60% OF THE SUBUNITS OF THE STROMAL RIDGE OF PSI [PHENOTYPE]", "interaction": "show", "category": "EXPRESSION/DETECTION/IDENTIFICATION"}},
        {"data": {"id": "edge1", "source": "A. THALIANA [ORGANISM]", "target": "(PSAD-1, PSAD1, AT4G02770)-1 [GENE IDENTIFIER]", "interaction": "mutant", "category": "OTHERS"}},
        {"data": {"id": "edge2", "source": "(PSAD-1, PSAD1, AT4G02770)-1 [GENE IDENTIFIER]", "target": "PSAD MRNA AND PROTEIN(S) [GENE]", "interaction": "affect levels of", "category": "REGULATION/CONTROL"}},
        {"data": {"id": "edge3", "source": "(PSAD-1, PSAD1, AT4G02770)-1 [GENE IDENTIFIER]", "target": "MRNA EXPRESSION OF MOST GENE(S) INVOLVED IN THE LIGHT PHASE OF PHOTOSYNTHESIS [GENE]", "interaction": "down-regulates", "category": "REPRESSION/INHIBITION/DECREASE/NEGATIVE REGULATION"}},
        {"data": {"id": "edge4", "source": "OXIDATION OF PHOTOSYSTEM I (PSI) [PHENOTYPE]", "target": "(PSAD-1, PSAD1, AT4G02770)-1 [GENE IDENTIFIER]", "interaction": "impaired in", "category": "REPRESSION/INHIBITION/DECREASE/NEGATIVE REGULATION"}},
        {"data": {"id": "edge5", "source": "(PSAD-1, PSAD1, AT4G02770)-1 [GENE IDENTIFIER]", "target": "INCREASED SENSITIVITY TO LIGHT STRESS [PHENOTYPE]", "interaction": "show", "category": "EXPRESSION/DETECTION/IDENTIFICATION"}},
        {"data": {"id": "edge6", "source": "PQ POOL [METABOLITE]", "target": "(PSAD-1, PSAD1, AT4G02770)-1 [GENE IDENTIFIER]", "interaction": "is over-reduced in", "category": "LOCALIZATION/CONTAINMENT/COMPOSITION"}},
        {"data": {"id": "edge7", "source": "(PSAD-1, PSAD1, AT4G02770)-1 [GENE IDENTIFIER]", "target": "PHOSPHORYLATION OF THYLAKOID PROTEIN(S) [TREATMENT]", "interaction": "analyzed for", "category": "EXPRESSION/DETECTION/IDENTIFICATION"}},
        {"data": {"id": "edge8", "source": "PLHCA4 [PROTEIN]", "target": "(PSAD-1, PSAD1, AT4G02770)-1 [GENE IDENTIFIER]", "interaction": "accumulates in", "category": "LOCALIZATION/CONTAINMENT/COMPOSITION"}},
        {"data": {"id": "edge9", "source": "130 MOST STRONGLY ATTENUATED GENE(S) [GENE]", "target": "(PSAD-1, PSAD1, AT4G02770)-1 [GENE IDENTIFIER]", "interaction": "downregulated in", "category": "REPRESSION/INHIBITION/DECREASE/NEGATIVE REGULATION"}},
        {"data": {"id": "edge10", "source": "(PSAD-1, PSAD1, AT4G02770)-1 [GENE IDENTIFIER]", "target": "GROWTH RATE [PHENOTYPE]", "interaction": "decreases", "category": "REPRESSION/INHIBITION/DECREASE/NEGATIVE REGULATION"}},
        {"data": {"id": "edge11", "source": "(PSAD-1, PSAD1, AT4G02770)-1 [GENE IDENTIFIER]", "target": "PHOTOSYNTHETIC ELECTRON TRANSPORT [PHENOTYPE, PROCESS]", "interaction": "affect", "category": "REGULATION/CONTROL"}},
        {"data": {"id": "edge12", "source": "(PSAD-1, PSAD1, AT4G02770)-1 [GENE IDENTIFIER]", "target": "PSI AND PSII POLYPEPTIDES [PROTEIN COMPLEX]", "interaction": "diminished", "category": "REPRESSION/INHIBITION/DECREASE/NEGATIVE REGULATION"}},
        {"data": {"id": "edge13", "source": "(PSAD-1, PSAD1, AT4G02770)-1 [GENE IDENTIFIER]", "target": "LIGHT-GREEN LEAF COLORATION [PHENOTYPE]", "interaction": "show", "category": "EXPRESSION/DETECTION/IDENTIFICATION"}},
    ]}

    return render_template('index.html', entities=entities, papers=papers, preview=preview)


@app.route('/help', methods=['GET'])
def help():
    return render_template('help.html')


@app.route('/features', methods=['GET'])
def features():
    return render_template('features.html')


@app.route('/favicon.ico', methods=['GET'])
def favicon():
    return send_from_directory(os.path.join(app.root_path, 'static'), 'favicon.ico', mimetype='image/vnd.microsoft.icon')


@app.route('/process-summary', methods=['POST'])
def process_summary():
    data = request.json
    summary = data.get('summary')
    user_input = data.get('user_input')
    temperature_input = data.get('temperature', 0.7)
    max_tokens_input = data.get('max_tokens', 512)
    top_p_input = data.get('top_p', 1.0)
    models = data.get('models')

    if not summary:
        return jsonify({"error": "Summary not provided"}), 400

    openai_api_key = os.getenv("OPENAI_API_KEY")
    if not openai_api_key:
        return jsonify({"error": "OpenAI API key not configured. Set OPENAI_API_KEY environment variable."}), 500

    if "gpt" in models:
        client = openai.OpenAI(api_key=openai_api_key)
    else:
        groq_api_key = os.getenv("GROQ_API_KEY")
        if not groq_api_key:
            return jsonify({"error": "Groq API key not configured."}), 500
        client = openai.OpenAI(base_url="https://api.groq.com/openai/v1", api_key=groq_api_key)

    def generate_stream():
        try:
            completion = client.chat.completions.create(
                model=models,
                messages=[
                    {"role": "system", "content": (
                        "You are an expert scientific assistant that generates detailed, "
                        "structured scientific reviews based on provided input and PMIDs. "
                        "Focus on plant science topics including plant biology, "
                        "plant-microbe interactions, plant genomics, and plant-disease associations. "
                        "Be accurate and thorough in your response."
                    )},
                    {"role": "user", "content": summary},
                    {"role": "user", "content": user_input + " If the prompt before this is not related to the input, please ignore it and reply please give a relevant prompt."}
                ],
                temperature=float(temperature_input),
                max_tokens=int(max_tokens_input),
                top_p=float(top_p_input),
                stream=True
            )
            for chunk in completion:
                delta_content = getattr(chunk.choices[0].delta, "content", "")
                if delta_content:
                    yield f"{delta_content}"
        except Exception as api_error:
            yield f"data: {json.dumps({'error': str(api_error)})}\n\n"

    return Response(generate_stream(), content_type='text/event-stream')


@app.route('/send-summary', methods=['POST'])
def send_summary():
    data = request.json
    summary = data.get('summary')
    if not summary:
        return jsonify({'status': 'error', 'message': 'Summary not provided'}), 400
    return jsonify({'status': 'success', 'message': 'Summary received', 'summary': summary})


@app.route('/form/<form_type>/<search_type>', methods=['POST'])
def form(form_type, search_type):
    query = request.form.get(form_type)
    selected_categories = request.form.getlist('category')
    if selected_categories:
        categories = {f'category_{i}': category for i, category in enumerate(selected_categories)}
        return redirect(url_for(search_type, query=query, **categories))
    return redirect(url_for(search_type, query=query))


def get_scientific_chunk(pmid, section=''):
    """Look up paper text by custom_id/title and section from MongoDB scientific_chunks collection.

    The custom_id (used as pmid in the edge data) contains the paper title.
    We look up the title from all_dic, then fetch section text from scientific_chunks.
    """
    pmid = str(pmid).strip()
    if not pmid:
        return None

    # Normalize section name to match DB keys
    section_map = {
        'ABSTRACT': 'ABSTRACT',
        'INTRO': 'INTRODUCTION',
        'INTRODUCTION': 'INTRODUCTION',
        'METHODS': 'METHODS',
        'RESULTS': 'RESULTS',
        'RESULTS_AND_DISCUSSION': 'RESULTS_AND_DISCUSSION',
        'DISCUSSION': 'DISCUSSION',
        'DISCUSS': 'DISCUSSION',
        'CONCLUSION': 'CONCLUSION',
        'CONCL': 'CONCLUSION',
        'TITLE': 'TITLE',
    }

    # Extract the paper title from all_dic using the custom_id
    all_dic = db["all_dic"]
    doc = all_dic.find_one({"custom_id": pmid}, {"title": 1})
    if not doc or not doc.get("title"):
        return None
    title = doc["title"]

    # Extract section from the custom_id suffix (e.g. "..._abstract", "..._results")
    # The section in the custom_id is after the last underscore of the hash
    pmid_section = ''
    parts = pmid.rsplit('_', 1)
    if len(parts) > 1:
        pmid_section = parts[-1].upper()

    # Determine which section to fetch
    requested_section = section.upper() if section else pmid_section
    db_section = section_map.get(requested_section, requested_section)

    # Try specific section first
    if db_section:
        chunk = scientific_chunks.find_one({"title": title, "section": {"$regex": db_section, "$options": "i"}}, {"_id": 0})
        if chunk and chunk.get("text"):
            return chunk["text"]

    # Otherwise return all available text for this title
    chunks = list(scientific_chunks.find({"title": title}, {"_id": 0}).sort("section", 1))
    if not chunks:
        return None
    parts = []
    for chunk in chunks:
        parts.append(f"[{chunk['section']}]\n{chunk['text']}")
    return '\n\n'.join(parts) if parts else None


@app.route('/process-text-withoutapi', methods=['POST'])
def process_text_withoutapi():
    data = request.get_json()
    pmid = data.get('pmid') or data.get('p_source', '')
    section = data.get('section', '')
    text_input = get_scientific_chunk(pmid, section)
    if not text_input:
        return jsonify({"text_input": None, "error": f"No paper text available for PMID {pmid}. The full text for this paper has not been downloaded yet."})
    return jsonify({"text_input": text_input})


@app.route('/process-text', methods=['POST'])
def process_text():
    data = request.get_json()
    if not data:
        return jsonify({"error": "Invalid JSON received"}), 400
    pmid = data.get('pmid') or data.get('p_source', '')
    section = data.get('section', '')
    text_input = get_scientific_chunk(pmid, section)
    source = data.get('source', '')
    interaction = data.get('interaction', '')
    target = data.get('target', '')

    if not text_input:
        return jsonify({"error": f"No paper text available for PMID {pmid}. The full text for this paper has not been downloaded yet."}), 404

    openai_api_key = os.getenv("OPENAI_API_KEY")
    if not openai_api_key:
        return jsonify({"error": "OpenAI API key not configured."}), 500

    try:
        client = openai.OpenAI(api_key=openai_api_key)

        def generate_stream():
            try:
                completion = client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[
                        {"role": "system", "content": (
                            "You are a scientific expert in plant biology and plant science research. "
                            "Your role is to validate whether a given source-target interaction is correctly derived from the provided scientific text. "
                            "Use logical reasoning, scientific knowledge, and textual evidence to assess the accuracy of the claimed relationship."
                        )},
                        {"role": "user", "content": f"**Scientific Text:**\n\"\"\"\n{text_input}\n\"\"\"\n\n"
                                f"**Proposed Relationship:**\n"
                                f"- **Source:** {source}\n"
                                f"- **Interaction:** {interaction}\n"
                                f"- **Target:** {target}\n\n"
                                "### Task:\n"
                                "- Validate whether the provided interaction correctly reflects the relationship described in the text.\n"
                                "- Quote the **exact statements** from the text that support or contradict the relationship.\n"},
                        {"role": "user", "content": (
                            "Respond in the following structured format:\n"
                            "- **Validation Status**: (Correct / Uncertain / Incorrect)\n"
                            "- **Supporting Evidence**: Quote exact sentences from the scientific text.\n"
                            "- **Explanation**: Justify the assessment.\n"
                            "- **Suggested Correction** (if applicable)"
                        )}
                    ],
                    temperature=0,
                    max_tokens=1000,
                    top_p=0,
                    stream=True
                )
                for chunk in completion:
                    delta_content = chunk.choices[0].delta.content if hasattr(chunk.choices[0].delta, 'content') else ''
                    if delta_content:
                        yield f"{delta_content}"
            except Exception as api_error:
                yield f"Error: {str(api_error)}"

        return Response(generate_stream(), content_type='text/event-stream')
    except Exception as e:
        return jsonify({"error": "Unexpected error", "details": str(e)}), 500


@app.route('/send-text', methods=['POST'])
def send_text():
    data = request.json
    text = data.get('text')
    if not text:
        return jsonify({'status': 'error', 'message': 'Text not provided'}), 400
    return jsonify({'status': 'success', 'message': 'Text received', 'text': text})


@app.route('/openai-edge-synonyms', methods=['POST'])
def openai_edge_synonyms():
    data = request.get_json(force=True)
    selected_groups = data.get('selectedGroups', [])
    edge_counts = data.get('edgeCounts', {})

    prompt_text = f"""
    The user has selected the following group: {selected_groups}.
    The dataset contains the following interaction types with their respective counts:
    {json.dumps(edge_counts, indent=2)}
    Your task is to find interactions from the list above that best fit the selected group.
    Only return **valid JSON** with this exact structure:
    {{
    "semantic_mappings": {{
        "group_name": ["matching_interaction1", "matching_interaction2", ...]
    }}
    }}
    """

    try:
        openai_api_key = os.getenv("OPENAI_API_KEY")
        if not openai_api_key:
            return jsonify({"error": "OpenAI API key not configured."}), 500
        client = openai.OpenAI(api_key=openai_api_key)
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt_text}],
            temperature=0.0, max_tokens=500, top_p=0
        )
        model_message = response.model_dump()['choices'][0]['message']['content'].strip()
        if model_message.startswith("```"):
            model_message = model_message.replace("```json", "").replace("```", "").strip()
        synonyms_json = json.loads(model_message)
        return jsonify(synonyms_json)
    except json.JSONDecodeError as e:
        return jsonify({"error": "GPT response was not valid JSON"}), 500
    except Exception as e:
        return jsonify({"error": str(e)}), 500


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080)
