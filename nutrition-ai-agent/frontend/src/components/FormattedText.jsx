import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

const sectionHeadings = new Set([
  "Summary",
  "Daily Calories & Macros",
  "7-Day Meal Plan",
  "Grocery List",
  "Habit & Adherence Tips",
  "Safety Notes",
]);

function normalizeForDisplay(text) {
  if (!text) return "";
  return text
    .split("\n")
    .map((line) => {
      const cleaned = line.trim();
      if (sectionHeadings.has(cleaned)) {
        return `## ${cleaned}`;
      }
      return cleaned;
    })
    .join("\n");
}

export default function FormattedText({ text }) {
  return (
    <div className="formatted-output">
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          h2: ({ ...props }) => <h5 className="fw-bold mt-3 mb-2" {...props} />,
          p: ({ ...props }) => <p className="mb-2" {...props} />,
          ul: ({ ...props }) => <ul className="mb-2" {...props} />,
          ol: ({ ...props }) => <ol className="mb-2" {...props} />,
          strong: ({ ...props }) => <strong className="fw-semibold" {...props} />,
        }}
      >
        {normalizeForDisplay(text)}
      </ReactMarkdown>
    </div>
  );
}
