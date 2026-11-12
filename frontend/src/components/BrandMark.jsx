/*
  Marca de Finly: el zorro de public/finly-fox.svg, tal cual (sin cambiarle
  el color). La URL la genera el plugin "finly-fox" de vite.config.js con un
  hash del archivo, así el navegador descarga la versión nueva cuando cambias
  el dibujo.
*/
import foxUrl from 'virtual:finly-fox'

export default function BrandMark({ className = '' }) {
  return (
    <span className={`brand-mark${className ? ` ${className}` : ''}`}>
      <img className="brand-mark-fox" src={foxUrl} alt="Finly" width="22" height="22" />
    </span>
  )
}
