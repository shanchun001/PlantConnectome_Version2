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
        case 'word':
            help_text = `
            <p>
            Find all entities that contain the search query as a <b>whole</b> word. For instance, if "CESA" is searched, the following entities will be identified:
                <ul style = 'color: green;'>
                    <li> CESA </li>
                    <li> CESA1 </li>
                    <li> CESA complex </li>
                </ul>
                However, it will not find entities such as:
                <br> <br>
                <ul style = 'color: red;'>
                    <li> cellulose (i.e., not containing CESA as a word) </li>
                </ul>
                </p>`;
            break;
        case 'exact':
            help_text = `
            <p>
                Finds the entity that <b>exactly</b> matches the search query. For instance, if "salicylic acid" is searched, the following entity will be found:
                <ul style = 'color: green;'>
                    <li> salicylic acid </li>
                </ul>
                However, it will not find entities such as:
                <br> <br>
                <ul style = 'color: red;'>
                    <li> salicylic acid signaling </li>
                    <li> methyl salicylic acid </li>
                </ul>
            </p>`;
            break;
        case 'substring':
            help_text = `
            <p>
                Finds all entities that contain the search query as a <b>substring</b>. For instance, if "Arabidop" is searched, this search will find the
                following entities:
                <ul style = 'color: green;'>
                    <li> Arabidopsis </li>
                    <li> Arabidopsis thaliana </li>
                    <li> Arabidopsis lyrata </li>
                </ul>
            </p>`;
            break;
        case 'non-alphanumeric':
            help_text = `
            <p>
                Finds all entities that contain the search query <b>followed by a non-alphanumeric character</b> (eg. "/", "-"). For instance, if "AT4G"
                is searched, this search will find the following entities:
                <ul style = 'color: green;'>
                    <li> AT4G02770 </li>
                    <li> AT4G18780 </li>
                </ul>
                However, it will not find entities such as:
                <br> <br>
                <ul style = 'color: red;'>
                    <li> AT5G01530 </li>
                </ul>
            </p>`;
            break;
        case 'paired-entity':
                help_text = `
                <p>
                    Finds all <b>paired entities</b> matches the search query split by "$". For instance, if "drought$ABA"
                    is searched, this search will find the following source and target pair entities:
                    <ul style = 'color: green;'>
                        <li> source node which contains: drought; target node which contains: ABA </li>
                        <li> source node which contains: ABA; target node which contains: drought </li>
                    </ul>
                    However, it will not find source and target pair entities such as:
                    <br> <br>
                    <ul style = 'color: red;'>
                        <li> source node which contains: drought; target node which contains: salicylic acid </li>
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
