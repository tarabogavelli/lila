import BookCard from "./BookCard";

export default function BookshelfPanel({ shelves }) {
  const shelfNames = Object.keys(shelves);

  if (shelfNames.length === 0) {
    return (
      <div className="bookshelves-empty">
        <p>Your shelves will appear here as Lila curates books for you.</p>
      </div>
    );
  }

  return (
    <div className="bookshelves">
      <h2 className="shelves-title">Your Shelves</h2>
      {shelfNames.map((name) => (
        <div key={name} className="shelf">
          <h3 className="shelf-name">{name}</h3>
          <div className="shelf-books">
            {shelves[name].map((book, i) => (
              <BookCard key={`${name}-${i}`} book={book} />
            ))}
          </div>
        </div>
      ))}
    </div>
  );
}
