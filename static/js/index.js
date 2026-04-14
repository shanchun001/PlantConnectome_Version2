// Get forms in order of gene-form, name-form, and title-form:
const forms = document.querySelectorAll('form');

const titleInput = document.getElementById("gene_id");

// Change placeholder text based on which button is being hovered over.
const setupButtonHoverEvents = () => {
    const buttonConfigs = [
        { value: 'Word', placeholder: "e.g., CESA (press Enter to search)", defaultPlaceholder: "e.g., CESA (press Enter to search)" },
        { value: 'Exact', placeholder: "e.g., salicylic acid (press Enter to search)", defaultPlaceholder: "e.g., salicylic acid (press Enter to search)" },
        { value: 'Substring', placeholder: "e.g., Arabidop (press Enter to search)", defaultPlaceholder: "e.g., Arabidop (press Enter to search)" },
        { value: 'Non-alphanumeric', placeholder: "e.g., AT4G (press Enter to search)", defaultPlaceholder: "e.g., AT4G (press Enter to search)" },
        { value: 'Paired-entity', placeholder: "e.g., drought$ABA (press Enter to search)", defaultPlaceholder: "e.g., drought$ABA (press Enter to search)" }
    ];

    buttonConfigs.forEach(config => {
        let button = document.querySelector(`input[value = ${config.value}]`);
        if (button) {
            button.addEventListener('mouseover', () => {
                titleInput.placeholder = config.placeholder;
            });
            button.addEventListener('mouseout', () => {
                titleInput.placeholder = config.defaultPlaceholder;
            });
        }
    });
}

// Attaches event listeners to the gene form.
const gene_form_listeners = () => {
    let form_buttons = forms[0].querySelectorAll('.button');
    let form_actions = (function() {
        let temp = [];
        form_buttons.forEach(button => {
            temp.push(button.getAttribute('formaction'));
        })
        return temp;
    })();

    for (let i = 0 ; i < form_buttons.length ; i++) {
        form_buttons[i].addEventListener('click', () => {
            submitGeneForm(event, forms[0], form_actions[i]);
        });
    }
}
// Methods for submitting the gene form via buttons:
// Function to show the loading icon and background overlay
function showLoading() {
    //document.getElementById('loading-icon').style.display = 'inline-block'; // Show the main loading icon
    document.getElementById('loading-text').style.display = 'inline-block';
    document.getElementById('loading-icon-small').style.display = 'inline-block'; // Show the small loading icon
}

// Function to hide the loading icon and background overlay
function hideLoading() {
    document.getElementById('loading-icon').style.display = 'none';
    document.getElementById('loading-text').style.display = 'none';
    document.getElementById('loading-icon-small').style.display = 'none';
}



// Attach the showLoading function to the form submission buttons
document.querySelectorAll('form .button').forEach(button => {
    button.addEventListener('click', showLoading);
});

function submitGeneForm(event, form, path) {
    // Default title values for different paths
    const defaultTitles = {
        '/form/gene_id/exact': 'salicylic acid',
        '/form/gene_id/normal': 'CESA',
        '/form/gene_id/substring': 'Arabidop',
        '/form/gene_id/paired_entity': 'drought$ABA',
        '/form/gene_id/non_alpha': 'AT4G'
    };

    // If the title input is empty, set it based on the path
    if (titleInput.value === "") {
        titleInput.value = defaultTitles[path] || ''; // Set to default if path matches, else keep it empty
    }

    form.submit();
}

function submitNameForm(event, form) {
    const titleInput = document.getElementById("author");
    if (titleInput.value === "") {
        titleInput.value = 'Mutwil M';
    }
    form.submit();
}

function submitTitleForm(event, form) {
    const titleInput = document.getElementById("title");
    if (titleInput.value === "") {
        titleInput.value = '38050352';
    }
    form.submit();
}


function submitFormWith(event, value) {
    event.preventDefault();
    // Submit the form with the clicked value
    const link = event.target;
    const form = link.closest('form');
    const input = form.querySelector('input[type="text"]');
    input.value = value;
    form.submit();
}

window.addEventListener('load', () => {
    setupButtonHoverEvents();
    gene_form_listeners();
    hideLoading();
    forms[1].setAttribute('onsubmit', `submitNameForm(event, forms[1])`);
    forms[2].setAttribute('onsubmit', `submitTitleForm(event, forms[2])`);
});

const loadingText = document.getElementById('loading-text');
loadingText.innerText = ''; // Clear the existing text

const words = "Loading in progress...".split(''); // Split into characters including spaces
let index = 0;

function typeEffect() {
    if (index < words.length) {
        if (words[index] === ' ') {
            loadingText.innerHTML += '&nbsp;'; // Add a non-breaking space
        } else {
            loadingText.innerText += words[index];
        }
        index++;
        setTimeout(typeEffect, 85); // Adjust speed of typing here
    } else {
        setTimeout(() => {
            loadingText.innerText = ''; // Clear text and restart typing effect
            index = 0;
            typeEffect();
        }, 1000); // Pause before restarting the typing effect
    }
}

typeEffect();


/*
This part of the file contains JavaScript for the help part of the landing page.
*/

// Selects the necessary HTML elements to change / attach event listeners to:
const help_information = document.querySelector('#help-text');
const help_buttons = document.querySelectorAll('.button-group')[1].querySelectorAll('.button');

// Change help information depending on which button is clicked:
const change_help_text = (button, text) => {
    /*
    Alters the appearance of the help button and the help text.
    */
    help_buttons.forEach(b => {
        if (b.innerText.toLowerCase() === text) {
            b.classList.remove('hollow');
        } else {
            b.classList.add('hollow');
        }
    })

    switch (text) {
        case 'gene / word':
            help_text = `
              <p>
                Find all entities where your query appears as a <em>standalone</em> word,
                even if it contains hyphens or other non-alphanumeric characters.
                For instance, if "CESA" is searched, the following entities will be identified:
              </p>
              <ul style="color: green;">
                <li>CESA</li>
                <li>Primary wall CESA-complex (hyphenated)</li>
                <li>CesA/CSL superfamily (slash-delimited)</li>
                <li>CESA genes</li>
              </ul>
              <p>However, it will not find entities such as:</p>
              <ul style="color: red;">
                <li>CESA3 (contains alphanumericals in the same word)</li>
                <li>ATCESA (embedded in a larger word)</li>
              </ul>
              <p>You can search for <em>Arabidopsis thaliana</em> genes by entering an AGI number or an alias. For example, 'CESA1' would return:</p>
              <ul style="color: green;">
                <li>(ATCESA1, CESA1, RSW1, AT4G32410, ANY1)</li>
                <li>(ATCESA1, CESA1, RSW1, AT4G32410, ANY1) mutant</li>
              </ul>`;
            break;
        case 'substring':
            help_text = `
            <p>
                Finds all entities that contain the search query. For instance, if "hair" is searched, this search will find the
                following entities:
                <ul style = 'color: green;'>
                    <li> root hair </li>
                    <li> root hairs </li>
                    <li> hairy roots </li>
                </ul>
            </p>`;
            break;
        default:
            help_text = `
            <p>
                Click one of the above buttons to find out more about each search function!
            </p>`;
            break;
    };
    help_information.innerHTML = help_text;
}

// Attach event listeners to each button:
help_buttons.forEach(button => {
    let button_text = button.innerText.toLowerCase();
    button.setAttribute('onclick', `change_help_text('${button}', '${button_text}')`);
    help_buttons[0].click();
})
