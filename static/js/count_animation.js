const animation_duration = 3000;
const frames_per_sec = 1000 / 60;
const num_frames = Math.round(animation_duration / frames_per_sec);
const ease_out = t => t * (2 - t);

const animate = (element) => {
    let frame = 0;
    const count_to = parseInt(element.innerHTML, 10);

    // Reserve the final width before animating to prevent text reflow
    const finalText = count_to.toLocaleString();
    element.style.minWidth = element.offsetWidth + 'px';
    element.innerText = '0';

    const counter = setInterval(() => {
        frame++;
        const progress = ease_out(frame / num_frames);
        const current_count = Math.round(count_to * progress);

        if (parseInt(element.innerText, 10) !== current_count) {
            element.innerText = current_count.toLocaleString();
        }

        if (frame === num_frames) {
            clearInterval(counter);
        }

    }, frames_per_sec);
};

window.addEventListener('load', () => {
    let to_animate = document.querySelectorAll('.count');
    to_animate.forEach(animate);
})
