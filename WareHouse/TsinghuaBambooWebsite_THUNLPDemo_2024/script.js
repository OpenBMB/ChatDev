document.addEventListener('DOMContentLoaded', function() {
    AOS.init({
        duration: 1000,
        once: true,
        offset: 100,
        disable: '.parallax-section' // Disable AOS for parallax section
    });

    const swiper = new Swiper('.hero-slider', {
        loop: true,
        speed: 1000,
        autoplay: {
            delay: 5000,
            disableOnInteraction: false,
        },
        pagination: {
            el: '.swiper-pagination',
            clickable: true,
        },
        navigation: {
            nextEl: '.swiper-button-next',
            prevEl: '.swiper-button-prev',
        },
    });

    const magneticLinks = document.querySelectorAll('.magnetic-link');

    magneticLinks.forEach(link => {
        link.addEventListener('mousemove', function(e) {
            const bounds = this.getBoundingClientRect();
            const mouseX = e.clientX - bounds.left;
            const mouseY = e.clientY - bounds.top;
            const centerX = bounds.width / 2;
            const centerY = bounds.height / 2;
            const deltaX = mouseX - centerX;
            const deltaY = mouseY - centerY;

            gsap.to(this, {
                x: deltaX * 0.3,
                y: deltaY * 0.3,
                duration: 0.3
            });
        });

        link.addEventListener('mouseleave', function() {
            gsap.to(this, {
                x: 0,
                y: 0,
                duration: 0.3
            });
        });
    });

    gsap.registerPlugin(ScrollTrigger);

    const timelineItems = document.querySelectorAll('.timeline-item');
    timelineItems.forEach((item, index) => {
        const tl = gsap.timeline({
            scrollTrigger: {
                trigger: item,
                start: "top center+=100",
                end: "bottom center",
                toggleActions: "play none none reverse"
            }
        });

        tl.from(item.querySelector('::before'), {
            scale: 0,
            opacity: 0,
            duration: 0.6,
            ease: "back.out(1.7)"
        });

        tl.from(item.querySelector('.timeline-content'), {
            x: index % 2 === 0 ? 50 : -50,
            opacity: 0,
            duration: 0.8,
            ease: "power2.out"
        }, "-=0.3");

        tl.from(item.querySelector('.timeline-period'), {
            y: 20,
            opacity: 0,
            duration: 0.5,
            ease: "power2.out"
        }, "-=0.4");
    });

    VanillaTilt.init(document.querySelectorAll('.digital-card'), {
        max: 15,
        speed: 400,
        glare: true,
        'max-glare': 0.2
    });

    document.querySelectorAll('a[href^="#"]').forEach(anchor => {
        anchor.addEventListener('click', function(e) {
            e.preventDefault();
            const target = document.querySelector(this.getAttribute('href'));
            if (target) {
                window.scrollTo({
                    top: target.offsetTop - 70,
                    behavior: 'smooth'
                });
            }
        });
    });

    const patternOverlay = document.querySelector('.pattern-overlay');
    window.addEventListener('mousemove', (e) => {
        const moveX = (e.clientX - window.innerWidth / 2) * 0.01;
        const moveY = (e.clientY - window.innerHeight / 2) * 0.01;
        gsap.to(patternOverlay, {
            x: moveX,
            y: moveY,
            duration: 1,
            ease: 'power2.out'
        });
    });

    const exhibitionCards = document.querySelectorAll('.exhibition-card');
    exhibitionCards.forEach(card => {
        card.addEventListener('mouseenter', () => {
            gsap.to(card, {
                y: -10,
                scale: 1.02,
                duration: 0.3,
                ease: 'power2.out'
            });
        });

        card.addEventListener('mouseleave', () => {
            gsap.to(card, {
                y: 0,
                scale: 1,
                duration: 0.3,
                ease: 'power2.out'
            });
        });
    });

    function createParticles() {
        const particleContainer = document.createElement('div');
        particleContainer.className = 'particle-container';
        document.body.appendChild(particleContainer);

        for (let i = 0; i < 50; i++) {
            const particle = document.createElement('div');
            particle.className = 'particle';
            particle.style.left = Math.random() * 100 + 'vw';
            particle.style.animationDelay = Math.random() * 5 + 's';
            particleContainer.appendChild(particle);
        }
    }

    document.addEventListener('DOMContentLoaded', () => {
        createParticles();
        
        const scrollElements = document.querySelectorAll('.bamboo-content > *');
        scrollElements.forEach(element => {
            element.style.opacity = '0';
            element.style.transform = 'translateX(-20px)';
        });

        const revealOnScroll = () => {
            scrollElements.forEach(element => {
                const elementTop = element.getBoundingClientRect().top;
                if (elementTop < window.innerHeight - 100) {
                    element.style.opacity = '1';
                    element.style.transform = 'translateX(0)';
                    element.style.transition = 'all 0.8s ease';
                }
            });
        };

        window.addEventListener('scroll', revealOnScroll);
        revealOnScroll();
    });

    function animateCounter(element) {
        const target = parseInt(element.dataset.target);
        const duration = 2000; 
        const step = target / (duration / 16); // 60fps
        let current = 0;

        const updateCounter = () => {
            current += step;
            if (current < target) {
                element.textContent = Math.floor(current);
                requestAnimationFrame(updateCounter);
            } else {
                element.textContent = target;
            }
        };

        updateCounter();
    }

    const observerOptions = {
        threshold: 0.5
    };

    const observer = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                const counters = entry.target.querySelectorAll('.counter');
                counters.forEach(counter => animateCounter(counter));
                observer.unobserve(entry.target);
            }
        });
    }, observerOptions);

    document.querySelectorAll('.stats-section').forEach(section => {
        observer.observe(section);
    });
});
