<script setup>
import { useRouter } from 'vue-router'

const router = useRouter()

const goToTutorial = () => {
  router.push('/tutorial')
}

const cubeColors = ['#aaffcd', '#99eaf9', '#a0c4ff']
const cubes = Array.from({ length: 80 }, (_, i) => ({
  id: i,
  left: `${Math.random() * 100}%`,
  top: `${Math.random() * 100}%`,
  size: `${Math.random() * 10 + 4}px`, // Wider size range
  color: cubeColors[Math.floor(Math.random() * cubeColors.length)],
  duration: `${Math.random() * 30 + 40}s`, // 30-60 seconds
  delay: `-${Math.random() * 60}s`, // Staggered delays
  blur: `${Math.random() * 2 + 1}px`, // Add blur
  opacity: Math.random() * 0.4 + 0.2, // Add opacity variation
  rotate: `${Math.random() * 360}deg`, // Add initial rotation
  scale: Math.random() * 1 + 0.7 // Add scale variation
}))
</script>

<template>
  <div class="home-view">
    <div class="cubes-background">
      <div 
        v-for="cube in cubes" 
        :key="cube.id"
        class="cube"
        :style="{
          left: cube.left,
          top: cube.top,
          width: cube.size,
          height: cube.size,
          backgroundColor: cube.color,
          boxShadow: `0 0 12px 2px ${cube.color}, 0 0 24px 4px ${cube.color}99`,
          animationDuration: cube.duration,
          animationDelay: cube.delay,
          filter: `blur(${cube.blur})`,
          opacity: cube.opacity,
          '--rotate': cube.rotate,
          '--scale': cube.scale
        }"
      ></div>
    </div>
    <div class="content-wrapper">
      <h1 class="title">
        <span class="title-line">ChatDev 2.0</span>
        <span class="title-line title-highlight">DevAll</span>
      </h1>
      
      <p class="introduction">
        ChatDev 2.0 - DevAll is a zero-code multi-agent platform for developing everything, with a workspace built for designing, visualizing, and running agent workflows.
      </p>

      <div class="actions">
        <button class="btn get-started-btn" @click="goToTutorial">
          Get Started →
        </button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.home-view {
  width: 100%;
  min-height: calc(100vh - 55px); /* Match sidebar height to avoid bottom gap */
  background-color: #1a1a1a;
  display: flex;
  justify-content: center;
  align-items: center;
  padding: 20px;
  box-sizing: border-box;
  font-family: 'Inter', sans-serif;
  position: relative;
  overflow: hidden;
}

.cubes-background {
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  pointer-events: none;
  z-index: 0;
}

/* Animated gradient overlay */
.cubes-background::before {
  content: '';
  position: absolute;
  inset: 0;
  background: radial-gradient(1200px 600px at 20% 30%, rgba(170, 255, 205, 0.15), transparent 60%),
              radial-gradient(1000px 500px at 80% 70%, rgba(160, 196, 255, 0.15), transparent 60%),
              linear-gradient(90deg, rgba(170,255,205,0.08), rgba(153,234,249,0.08), rgba(160,196,255,0.08));
  filter: blur(2px);
  animation: bgFlow 18s ease-in-out infinite;
}

@keyframes bgFlow {
  0% {
    transform: translate3d(0, 0, 0) scale(1);
    opacity: 0.8;
  }
  50% {
    transform: translate3d(-2%, 1%, 0) scale(1.02);
    opacity: 1;
  }
  100% {
    transform: translate3d(0, 0, 0) scale(1);
    opacity: 0.8;
  }
}

.cube {
  position: absolute;
  border-radius: 4px;
  transition: filter 0.3s, opacity 0.3s, transform 0.3s;
  animation: unifiedCubeAnim 18s linear infinite;
  will-change: transform, opacity, filter;
  /* Combined transform: initial angle and scale come from CSS variables */
  --rotate: 0deg;
  --scale: 1;
}

.cube:hover {
  filter: blur(0.5px) brightness(1.3) drop-shadow(0 0 8px #fff8);
  opacity: 0.7;
  transform: scale(1.2) rotate(10deg) !important;
  z-index: 2;
}

@keyframes unifiedCubeAnim {
  0% {
    opacity: 0.1;
    transform:
      translate3d(0, 0, 0)
      rotate(var(--rotate, 0deg))
      scale(var(--scale, 1));
  }
  20% {
    opacity: 0.3;
    transform:
      translate3d(10px, -20px, 0)
      rotate(calc(var(--rotate, 0deg) + 72deg))
      scale(calc(var(--scale, 1) * 1.05));
  }
  40% {
    opacity: 0.5;
    transform:
      translate3d(-20px, 60px, 0)
      rotate(calc(var(--rotate, 0deg) + 144deg))
      scale(calc(var(--scale, 1) * 1.1));
  }
  60% {
    opacity: 0.4;
    transform:
      translate3d(50px, 30px, 0)
      rotate(calc(var(--rotate, 0deg) + 216deg))
      scale(calc(var(--scale, 1) * 0.95));
  }
  80% {
    opacity: 0.3;
    transform:
      translate3d(-30px, -40px, 0)
      rotate(calc(var(--rotate, 0deg) + 288deg))
      scale(calc(var(--scale, 1) * 1.08));
  }
  100% {
    opacity: 0.1;
    transform:
      translate3d(0, 0, 0)
      rotate(calc(var(--rotate, 0deg) + 360deg))
      scale(var(--scale, 1));
  }
}

/* Background cubes drift slowly */
@keyframes drift {
  0% {
    transform: translate3d(0, 0, 0);
  }
  25% {
    transform: translate3d(2px, -2px, 0);
  }
  50% {
    transform: translate3d(-2px, 6px, 0);
  }
  75% {
    transform: translate3d(5px, 3px, 0);
  }
  100% {
    transform: translate3d(0, 0, 0);
  }
}

.content-wrapper {
  max-width: 900px;
  text-align: center;
  display: flex;
  flex-direction: column;
  align-items: center;
  position: relative;
  z-index: 1;
}

.title {
  font-size: 76px;
  font-weight: 900;
  line-height: 1.25;
  margin: 0 0 24px 0;
  letter-spacing: -1.5px;
  display: flex;
  flex-direction: column;
  align-items: center;
}

.title-line {
  color: #f2f2f2;
}

.title-highlight {
  background: linear-gradient(
    90deg,
    #aaffcd,
    #99eaf9,
    #a0c4ff
  );
  background-clip: text;
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
}

.introduction {
  font-size: 22px;
  color: rgba(235, 235, 235, 0.6);
  line-height: 1.5;
  max-width: 700px;
  margin: 0 auto 40px;
}

.actions {
  display: flex;
  gap: 18px;
  justify-content: center;
}

.btn {
  border: none;
  padding: 14px 32px;
  font-size: 16px;
  font-weight: 600;
  border-radius: 50px;
  cursor: pointer;
  transition: all 0.2s ease;
  text-decoration: none;
}

.secondary-btn {
  background-color: #2f2f2f;
  color: #f2f2f2;
}

.secondary-btn:hover {
  background-color: #3a3a3a;
  transition: all 0.3s ease;
}

.get-started-btn {
  color: #1a1a1a;
  background: linear-gradient(
    90deg,
    #aaffcd,
    #99eaf9,
    #a0c4ff
  );
  animation: gradientShift 4s ease-in-out infinite;
  background-size: 200% 100%;
  position: relative;
  z-index: 1;
}

.get-started-btn:hover {
  transform: translateY(-1px);
  box-shadow: 0 4px 15px rgba(0, 0, 0, 0.4);
}

@keyframes gradientShift {
  0%, 100% {
    background-position: 0% 0%;
  }
  50% {
    background-position: 100% 0%;
  }
}

@media (max-width: 768px) {
  .title {
    font-size: 42px;
  }
  
  .introduction {
    font-size: 18px;
  }
  
  .actions {
    flex-direction: column;
  }
}
</style>
