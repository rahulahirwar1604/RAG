// Initialize particles.js
particlesJS('particles-js', {
    particles: {
        number: { value: 100, density: { enable: true, value_area: 800 } },
        color: { value: ["#3b82f6", "#8b5cf6", "#ffffff", "#6ea5ff"] },
        shape: { type: "circle" },
        opacity: { value: 0.7, random: true, anim: { enable: true, speed: 1, opacity_min: 0.3, sync: false } },
        size: { value: 4, random: true, anim: { enable: true, speed: 2, size_min: 1, sync: false } },
        line_linked: { enable: true, distance: 150, color: "#3b82f6", opacity: 0.3, width: 1 },
        move: { enable: true, speed: 3, direction: "none", random: true, straight: false, out_mode: "out", bounce: false, attract: { enable: true, rotateX: 600, rotateY: 1200 } }
    },
    interactivity: {
        detect_on: "canvas",
        events: { onhover: { enable: true, mode: "grab" }, onclick: { enable: true, mode: "push" }, resize: true },
        modes: { grab: { distance: 200, line_linked: { opacity: 0.8 } }, bubble: { distance: 400, size: 8, duration: 2, opacity: 0.8, speed: 3 }, repulse: { distance: 200, duration: 0.4 }, push: { particles_nb: 4 }, remove: { particles_nb: 2 } }
    },
    retina_detect: true
});

// Register ScrollTrigger plugin
gsap.registerPlugin(ScrollTrigger);

// Initial load animation
const tl = gsap.timeline();
tl.from('.badge', { opacity: 0, y: 20, duration: 0.5 })
  .from('.hero-title', { opacity: 0, y: 30, duration: 0.7 }, '-=0.2')
  .from('.hero-desc', { opacity: 0, y: 20, duration: 0.6 }, '-=0.3')
  .from('.hero-actions', { opacity: 0, y: 20, duration: 0.5 }, '-=0.2')
  .from('.hero-visual', { opacity: 0, scale: 0.94, duration: 0.8, ease: 'back.out(1.2)' }, '-=0.4')
  .from('.navbar', { opacity: 0, y: -30, duration: 0.6 }, 0);

// Stats animation
gsap.from('.stat-item', { 
    scrollTrigger: { trigger: '.stats', start: 'top 80%' }, 
    opacity: 0, y: 30, stagger: 0.1, duration: 0.7 
});

// Feature banners animation
gsap.set(['#architecture-banner', '.features-container .feature-banner'], { opacity: 1, y: 0 });

gsap.from('#architecture-banner', { 
    scrollTrigger: { trigger: '#architecture-banner', start: 'top 85%', toggleActions: 'play none none none' }, 
    opacity: 0, y: 30, duration: 0.7 
});

gsap.from('.features-container .feature-banner', { 
    scrollTrigger: { trigger: '.features-container', start: 'top 80%', toggleActions: 'play none none none' }, 
    opacity: 0, y: 30, stagger: 0.15, duration: 0.7 
});

// Timeline animation
gsap.from('.timeline-step', { 
    scrollTrigger: { trigger: '.timeline', start: 'top 80%' }, 
    opacity: 0, x: -20, stagger: 0.15, duration: 0.6 
});

// Use cases animation
gsap.from('.use-case-card', { 
    scrollTrigger: { trigger: '.use-case-grid', start: 'top 80%' }, 
    opacity: 0, scale: 0.95, stagger: 0.1, duration: 0.6 
});

// Pricing cards animation
gsap.set('.pricing-card', { opacity: 1, y: 0 });

gsap.from('.pricing-card', { 
    scrollTrigger: { trigger: '.pricing-grid', start: 'top 95%', toggleActions: 'play none none none' }, 
    opacity: 0, y: 30, stagger: 0.15, duration: 0.7
});

// Testimonials animation
gsap.from('.testimonial-card', { 
    scrollTrigger: { trigger: '.testimonial-grid', start: 'top 80%' }, 
    opacity: 0, y: 40, stagger: 0.12, duration: 0.7 
});

// FAQ animation
gsap.from('.faq-item', { 
    scrollTrigger: { trigger: '.faq-grid', start: 'top 80%' }, 
    opacity: 0, y: 20, stagger: 0.1, duration: 0.5 
});

// CTA animation
gsap.from('.cta-section', { 
    scrollTrigger: { trigger: '.cta-section', start: 'top 85%' }, 
    opacity: 0, scale: 0.96, duration: 0.9, ease: 'power3.out' 
});

// Button hover effects
document.querySelectorAll('.btn-primary, .btn-outline').forEach(btn => {
    btn.addEventListener('mouseenter', () => gsap.to(btn, { scale: 1.02, duration: 0.2 }));
    btn.addEventListener('mouseleave', () => gsap.to(btn, { scale: 1, duration: 0.2 }));
});

// Modal functionality
const modal = document.getElementById('customModal');
const modalMsg = document.getElementById('modalMessage');

function showModal(msg) { 
    modalMsg.textContent = msg; 
    modal.classList.add('active'); 
}

function hideModal() { 
    modal.classList.remove('active'); 
}

document.getElementById('modalCloseBtn').addEventListener('click', hideModal);
modal.addEventListener('click', e => { 
    if (e.target === modal) hideModal(); 
});

// Button click handlers
document.getElementById('cta-main').addEventListener('click', () => location.href = "http://localhost:5173/");
document.getElementById('cta-footer').addEventListener('click', () => location.href = "http://localhost:5173/");
document.querySelectorAll('.starterBtn').forEach(b => b.addEventListener('click', () => location.href = "http://localhost:5173/"));
document.querySelectorAll('.proBtn').forEach(b => b.addEventListener('click', () => showModal('Available Soon')));
document.querySelectorAll('.enterpriseBtn').forEach(b => b.addEventListener('click', () => showModal('Available Soon')));