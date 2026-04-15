export default function BookCard({ book }) {
  const fallbackCover = book.isbn
    ? `https://covers.openlibrary.org/b/isbn/${book.isbn}-M.jpg`
    : null;
  const coverSrc = book.cover_url || fallbackCover;

  return (
    <div className="book-card">
      <div className="book-cover">
        {coverSrc ? (
          <img
            src={coverSrc}
            alt={`Cover of ${book.title}`}
            onError={(e) => {
              if (book.isbn && !e.target.src.includes("openlibrary")) {
                e.target.src = `https://covers.openlibrary.org/b/isbn/${book.isbn}-M.jpg`;
              } else {
                e.target.style.display = "none";
                e.target.nextElementSibling.style.display = "flex";
              }
            }}
          />
        ) : null}
        <div
          className="book-cover-placeholder"
          style={{ display: coverSrc ? "none" : "flex" }}
        >
          <span>{book.title?.[0] || "?"}</span>
        </div>
      </div>
      <div className="book-info">
        <p className="book-title">{book.title}</p>
        <p className="book-author">{book.author}</p>
      </div>
    </div>
  );
}
