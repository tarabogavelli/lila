const TOOL_LABELS = {
  search_books: "Searching for books",
  fetch_book_reviews: "Looking up reviews",
  add_to_shelf: "Adding to your shelf",
  get_shelf: "Checking your shelf",
  list_shelves: "Looking at your shelves",
  query_literary_knowledge: "Consulting the stacks",
  fetch_goodreads_reviews: "Reading Goodreads reviews",
  query_course_notes: "Checking course notes",
  rename_shelf: "Renaming shelf",
  remove_from_shelf: "Removing from shelf",
};

export default function ToolCallChip({ name }) {
  const label = TOOL_LABELS[name] || name;

  return <span className="tool-call-chip">{label}...</span>;
}
