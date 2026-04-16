import BookCard from "./BookCard";

export default function BookshelfPanel({ shelves }) {
  const shelfNames = Object.keys(shelves);

  if (shelfNames.length === 0) {
    return null;
  }

  return (
    <div className="bookshelves">
      <h2 className="shelves-title">Shelves</h2>
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
