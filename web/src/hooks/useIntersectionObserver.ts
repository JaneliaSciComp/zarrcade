/**
 * Observe when an element scrolls into the viewport. Disconnects once
 * seen — used for one-shot lazy work (e.g. fetching thumbnails).
 */

import { useEffect, useRef, useState } from 'react';

export function useIntersectionObserver<T extends Element>(
  options?: IntersectionObserverInit
) {
  const ref = useRef<T | null>(null);
  const [inView, setInView] = useState(false);

  useEffect(() => {
    if (inView) return;
    const el = ref.current;
    if (!el) return;

    const observer = new IntersectionObserver(([entry]) => {
      if (entry.isIntersecting) {
        setInView(true);
        observer.disconnect();
      }
    }, options);

    observer.observe(el);
    return () => observer.disconnect();
  }, [inView, options]);

  return { ref, inView };
}
