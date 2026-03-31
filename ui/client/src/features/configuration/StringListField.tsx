import { useState, KeyboardEvent } from "react";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { FaPlus, FaTimes } from "react-icons/fa";

interface StringListFieldProps {
  value: string[];
  onChange: (value: string[]) => void;
  placeholder?: string;
}

export default function StringListField({
  value,
  onChange,
  placeholder,
}: StringListFieldProps) {
  const [inputValue, setInputValue] = useState("");

  const addItem = () => {
    const trimmed = inputValue.trim().toLowerCase();
    if (!trimmed) return;
    if (value.includes(trimmed)) {
      setInputValue("");
      return;
    }
    onChange([...value, trimmed]);
    setInputValue("");
  };

  const removeItem = (index: number) => {
    onChange(value.filter((_, i) => i !== index));
  };

  const handleKeyDown = (e: KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Enter") {
      e.preventDefault();
      addItem();
    }
  };

  return (
    <div className="space-y-3">
      {/* Tag chips */}
      {value.length > 0 && (
        <div className="flex flex-wrap gap-2">
          {value.map((item, index) => (
            <Badge
              key={`${item}-${index}`}
              variant="secondary"
              className="pl-3 pr-1 py-1.5 text-sm flex items-center gap-1.5 bg-background-dark border border-gray-700"
            >
              <span className="font-mono">{item}</span>
              <button
                type="button"
                onClick={() => removeItem(index)}
                className="ml-1 p-0.5 rounded-full hover:bg-gray-600 transition-colors"
              >
                <FaTimes className="w-2.5 h-2.5 text-gray-400 hover:text-white" />
              </button>
            </Badge>
          ))}
        </div>
      )}

      {/* Add input */}
      <div className="flex gap-2">
        <Input
          value={inputValue}
          onChange={(e) => setInputValue(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder={placeholder || "Type and press Enter to add"}
          className="bg-background-dark flex-1"
        />
        <Button
          type="button"
          variant="outline"
          size="sm"
          onClick={addItem}
          disabled={!inputValue.trim()}
          className="px-3"
        >
          <FaPlus className="w-3 h-3 mr-1" />
          Add
        </Button>
      </div>
    </div>
  );
}
