import React, { useState, useRef, useCallback } from 'react';

interface Card3DProps {
  children: React.ReactNode;
  className?: string;
  intensity?: number; // How much it tilts
  style?: React.CSSProperties;
}

export default function Card3D({ children, className = '', intensity = 10, style }: Card3DProps) {
  const [rotation, setRotation] = useState({ x: 0, y: 0 });
  const [glarePos, setGlarePos] = useState({ x: 50, y: 50 });
  const [isHovered, setIsHovered] = useState(false);
  const cardRef = useRef<HTMLDivElement>(null);

  const handleMouseMove = useCallback((e: React.MouseEvent<HTMLDivElement>) => {
    if (!cardRef.current) return;

    const rect = cardRef.current.getBoundingClientRect();
    const width = rect.width;
    const height = rect.height;

    const mouseX = e.clientX - rect.left;
    const mouseY = e.clientY - rect.top;

    // Calculate rotation (-intensity to +intensity)
    const rotateX = ((mouseY / height) - 0.5) * -intensity;
    const rotateY = ((mouseX / width) - 0.5) * intensity;

    setRotation({ x: rotateX, y: rotateY });
    
    // Calculate glare position in percentage
    const glareX = (mouseX / width) * 100;
    const glareY = (mouseY / height) * 100;
    setGlarePos({ x: glareX, y: glareY });
  }, [intensity]);

  const handleMouseEnter = () => setIsHovered(true);
  const handleMouseLeave = () => {
    setIsHovered(false);
    setRotation({ x: 0, y: 0 });
  };

  return (
    <div
      ref={cardRef}
      className={`glass-card relative ${className}`}
      onMouseMove={handleMouseMove}
      onMouseEnter={handleMouseEnter}
      onMouseLeave={handleMouseLeave}
      style={{
        ...(style ?? {}),
        transform: isHovered
          ? `perspective(1000px) rotateX(${rotation.x}deg) rotateY(${rotation.y}deg) translateY(-8px)`
          : 'perspective(1000px) rotateX(0deg) rotateY(0deg) translateY(0)',
        // @ts-ignore
        '--mouse-x': `${glarePos.x}%`,
        // @ts-ignore
        '--mouse-y': `${glarePos.y}%`,
      }}
    >
      <div className="card-glare" />
      <div className="relative z-10 w-full h-full">
        {children}
      </div>
    </div>
  );
}
