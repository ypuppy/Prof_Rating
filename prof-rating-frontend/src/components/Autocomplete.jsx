import { useEffect, useLayoutEffect, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import './Autocomplete.css';

const DEBOUNCE_MS = 150;

/**
 * A text input with a suggestion list. The user can still type anything;
 * suggestions only help them pick a consistent value.
 *
 * fetchSuggestions(query) -> Promise<item[]>
 * renderItem(item)        -> { primary, secondary? }
 * onSelect(item)          -> called when a suggestion is picked (mouse or Enter)
 */
export default function Autocomplete({
  id,
  value,
  onChange,
  onSelect,
  fetchSuggestions,
  renderItem,
  minChars = 0,
  placeholder,
  className = 'form-input',
  maxLength,
  autoFocus,
}) {
  const [items, setItems] = useState([]);
  const [open, setOpen] = useState(false);
  const [activeIndex, setActiveIndex] = useState(-1);
  const timer = useRef(null);
  const latestRequest = useRef(0);
  const inputRef = useRef(null);
  const listRef = useRef(null);

  useEffect(() => () => clearTimeout(timer.current), []);

  // The list is rendered into <body> so a modal's overflow can't clip it.
  // Keep it pinned under the input while the page or modal scrolls.
  useLayoutEffect(() => {
    if (!open) return;
    const place = () => {
      const input = inputRef.current;
      const list = listRef.current;
      if (!input || !list) return;
      const r = input.getBoundingClientRect();
      list.style.top = `${r.bottom + 6}px`;
      list.style.left = `${r.left}px`;
      list.style.width = `${r.width}px`;
    };
    place();
    window.addEventListener('resize', place);
    window.addEventListener('scroll', place, true); // capture: also catches scrolling inside the modal
    return () => {
      window.removeEventListener('resize', place);
      window.removeEventListener('scroll', place, true);
    };
  }, [open, items]);

  const search = (query) => {
    clearTimeout(timer.current);
    if (query.trim().length < minChars) {
      setItems([]);
      setOpen(false);
      return;
    }
    timer.current = setTimeout(async () => {
      // Only the newest request may update the list, even if an older one answers last
      const requestId = ++latestRequest.current;
      try {
        const results = await fetchSuggestions(query.trim());
        if (requestId !== latestRequest.current) return;
        setItems(results);
        setActiveIndex(-1);
        setOpen(results.length > 0);
      } catch {
        if (requestId === latestRequest.current) setOpen(false);
      }
    }, DEBOUNCE_MS);
  };

  const pick = (item) => {
    onSelect(item);
    setOpen(false);
    setActiveIndex(-1);
  };

  const handleKeyDown = (e) => {
    if (!open || items.length === 0) return;
    if (e.key === 'ArrowDown') {
      e.preventDefault();
      setActiveIndex((i) => (i + 1) % items.length);
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      setActiveIndex((i) => (i <= 0 ? items.length - 1 : i - 1));
    } else if (e.key === 'Enter' && activeIndex >= 0) {
      e.preventDefault(); // pick the suggestion instead of submitting the form
      pick(items[activeIndex]);
    } else if (e.key === 'Escape') {
      setOpen(false);
    }
  };

  const listId = `${id}-suggestions`;

  return (
    <div className="autocomplete">
      <input
        ref={inputRef}
        id={id}
        type="text"
        className={className}
        placeholder={placeholder}
        maxLength={maxLength}
        autoFocus={autoFocus}
        autoComplete="off"
        value={value}
        role="combobox"
        aria-autocomplete="list"
        aria-expanded={open}
        aria-controls={listId}
        aria-activedescendant={open && activeIndex >= 0 ? `${listId}-${activeIndex}` : undefined}
        onChange={(e) => {
          onChange(e.target.value);
          search(e.target.value);
        }}
        onFocus={() => search(value)}
        onBlur={() => setOpen(false)}
        onKeyDown={handleKeyDown}
      />
      {open && createPortal(
        <ul className="autocomplete-list" id={listId} role="listbox" ref={listRef}>
          {items.map((item, i) => {
            const { primary, secondary } = renderItem(item);
            return (
              <li
                key={`${primary}-${i}`}
                id={`${listId}-${i}`}
                role="option"
                aria-selected={i === activeIndex}
                className={`autocomplete-option${i === activeIndex ? ' is-active' : ''}`}
                // mousedown, not click: click would fire after the input's blur closed the list
                onMouseDown={(e) => {
                  e.preventDefault();
                  pick(item);
                }}
                onMouseEnter={() => setActiveIndex(i)}
              >
                <span className="autocomplete-primary">{primary}</span>
                {secondary && <span className="autocomplete-secondary">{secondary}</span>}
              </li>
            );
          })}
        </ul>,
        document.body
      )}
    </div>
  );
}
