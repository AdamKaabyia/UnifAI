import React, { useState } from 'react';
import yaml from 'js-yaml';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Badge } from '@/components/ui/badge';
import { AlertCircle, Plus, X } from 'lucide-react';

interface CreateTemplateDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onSubmit: (data: {
    draft: Record<string, any>;
    placeholders: Record<string, any>;
    metadata: Record<string, any>;
  }) => Promise<void>;
  isSubmitting: boolean;
}

export const CreateTemplateDialog: React.FC<CreateTemplateDialogProps> = ({
  open,
  onOpenChange,
  onSubmit,
  isSubmitting,
}) => {
  const [draftYaml, setDraftYaml] = useState('');
  const [placeholdersJson, setPlaceholdersJson] = useState('{\n  "categories": []\n}');
  const [author, setAuthor] = useState('');
  const [category, setCategory] = useState('');
  const [version, setVersion] = useState('1.0.0');
  const [tagInput, setTagInput] = useState('');
  const [tags, setTags] = useState<string[]>([]);
  const [capabilityInput, setCapabilityInput] = useState('');
  const [capabilities, setCapabilities] = useState<string[]>([]);
  const [parseError, setParseError] = useState<string | null>(null);

  const handleAddItem = (
    value: string,
    list: string[],
    setList: React.Dispatch<React.SetStateAction<string[]>>,
    setInput: React.Dispatch<React.SetStateAction<string>>,
  ) => {
    const trimmed = value.trim();
    if (trimmed && !list.includes(trimmed)) {
      setList([...list, trimmed]);
      setInput('');
    }
  };

  const handleAddTag = () => handleAddItem(tagInput, tags, setTags, setTagInput);
  const handleAddCapability = () => handleAddItem(capabilityInput, capabilities, setCapabilities, setCapabilityInput);

  const handleSubmit = async () => {
    setParseError(null);

    let draft: Record<string, any>;
    try {
      draft = yaml.load(draftYaml) as Record<string, any>;
      if (!draft || typeof draft !== 'object') {
        setParseError('Blueprint YAML must be a valid YAML object.');
        return;
      }
    } catch (e: any) {
      setParseError(`Blueprint YAML parse error: ${e.message}`);
      return;
    }

    let placeholders: Record<string, any>;
    try {
      placeholders = JSON.parse(placeholdersJson);
      if (!placeholders || typeof placeholders !== 'object' || Array.isArray(placeholders)) {
        setParseError('Placeholders JSON must be a JSON object.');
        return;
      }
    } catch (e: any) {
      setParseError(`Placeholders JSON parse error: ${e.message}`);
      return;
    }

    const metadata = {
      author: author || undefined,
      category: category || undefined,
      version,
      tags,
      output_capabilities: capabilities,
      is_public: true,
    };

    await onSubmit({ draft, placeholders, metadata });
  };

  const resetForm = () => {
    setDraftYaml('');
    setPlaceholdersJson('{\n  "categories": []\n}');
    setAuthor('');
    setCategory('');
    setVersion('1.0.0');
    setTagInput('');
    setTags([]);
    setCapabilityInput('');
    setCapabilities([]);
    setParseError(null);
  };

  const handleClose = () => {
    if (!isSubmitting) {
      resetForm();
      onOpenChange(false);
    }
  };

  React.useEffect(() => {
    if (!open) resetForm();
  }, [open]);

  return (
    <Dialog open={open} onOpenChange={handleClose}>
      <DialogContent className="max-w-4xl max-h-[90vh] flex flex-col bg-background-card border-gray-800">
        <DialogHeader>
          <DialogTitle className="text-lg font-heading">Add Template</DialogTitle>
          <DialogDescription className="text-gray-400">
            Create a new workflow template. Paste the blueprint YAML, define placeholders, and set metadata.
          </DialogDescription>
        </DialogHeader>

        <Tabs defaultValue="metadata" className="flex-1 overflow-hidden flex flex-col">
          <TabsList className="bg-background-dark border border-gray-800">
            <TabsTrigger value="metadata">Metadata</TabsTrigger>
            <TabsTrigger value="blueprint">Blueprint (YAML)</TabsTrigger>
            <TabsTrigger value="placeholders">Placeholders (JSON)</TabsTrigger>
          </TabsList>

          <TabsContent value="metadata" className="flex-1 overflow-auto mt-4 space-y-4 pr-2">
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label className="text-gray-300">Author</Label>
                <Input
                  value={author}
                  onChange={(e) => setAuthor(e.target.value)}
                  placeholder="e.g. UnifAI"
                  className="input-dark-theme bg-black/50 border-gray-800 text-gray-200 placeholder:text-gray-500"
                />
              </div>
              <div className="space-y-2">
                <Label className="text-gray-300">Category</Label>
                <Input
                  value={category}
                  onChange={(e) => setCategory(e.target.value)}
                  placeholder="e.g. SRE & Incident Response"
                  className="input-dark-theme bg-black/50 border-gray-800 text-gray-200 placeholder:text-gray-500"
                />
              </div>
            </div>

            <div className="space-y-2">
              <Label className="text-gray-300">Version</Label>
              <Input
                value={version}
                onChange={(e) => setVersion(e.target.value)}
                placeholder="1.0.0"
                className="input-dark-theme bg-black/50 border-gray-800 text-gray-200 placeholder:text-gray-500 max-w-[200px]"
              />
            </div>

            <div className="space-y-2">
              <Label className="text-gray-300">Tags</Label>
              <div className="flex gap-2">
                <Input
                  value={tagInput}
                  onChange={(e) => setTagInput(e.target.value)}
                  onKeyDown={(e) => e.key === 'Enter' && (e.preventDefault(), handleAddTag())}
                  placeholder="Add a tag..."
                  className="input-dark-theme bg-black/50 border-gray-800 text-gray-200 placeholder:text-gray-500"
                />
                <Button type="button" variant="outline" size="sm" onClick={handleAddTag} className="border-gray-700">
                  <Plus className="h-3 w-3" />
                </Button>
              </div>
              {tags.length > 0 && (
                <div className="flex flex-wrap gap-1 mt-1">
                  {tags.map((tag) => (
                    <Badge key={tag} variant="secondary" className="text-xs bg-primary/10 text-primary">
                      #{tag}
                      <button aria-label={`Remove tag ${tag}`} onClick={() => setTags(tags.filter(t => t !== tag))} className="ml-1 hover:text-white">
                        <X className="h-2.5 w-2.5" />
                      </button>
                    </Badge>
                  ))}
                </div>
              )}
            </div>

            <div className="space-y-2">
              <Label className="text-gray-300">Output Capabilities</Label>
              <div className="flex gap-2">
                <Input
                  value={capabilityInput}
                  onChange={(e) => setCapabilityInput(e.target.value)}
                  onKeyDown={(e) => e.key === 'Enter' && (e.preventDefault(), handleAddCapability())}
                  placeholder="Add a capability..."
                  className="input-dark-theme bg-black/50 border-gray-800 text-gray-200 placeholder:text-gray-500"
                />
                <Button type="button" variant="outline" size="sm" onClick={handleAddCapability} className="border-gray-700">
                  <Plus className="h-3 w-3" />
                </Button>
              </div>
              {capabilities.length > 0 && (
                <div className="flex flex-wrap gap-1 mt-1">
                  {capabilities.map((cap) => (
                    <Badge key={cap} variant="secondary" className="text-xs bg-primary/10 text-primary">
                      {cap}
                      <button aria-label={`Remove capability ${cap}`} onClick={() => setCapabilities(capabilities.filter(c => c !== cap))} className="ml-1 hover:text-white">
                        <X className="h-2.5 w-2.5" />
                      </button>
                    </Badge>
                  ))}
                </div>
              )}
            </div>
          </TabsContent>

          <TabsContent value="blueprint" className="flex-1 overflow-hidden mt-4">
            <Textarea
              value={draftYaml}
              onChange={(e) => setDraftYaml(e.target.value)}
              placeholder={"# Blueprint YAML\n# Must include: name, description, providers, llms, tools, nodes, plan\nname: My Template\ndescription: ...\nllms:\n  - rid: llm_rid\n    name: ...\nnodes:\n  - rid: ...\nplan:\n  - uid: ..."}
              className="h-[400px] font-mono text-xs bg-black/50 border-gray-800 text-gray-200 placeholder:text-gray-600 resize-none"
              spellCheck={false}
            />
          </TabsContent>

          <TabsContent value="placeholders" className="flex-1 overflow-hidden mt-4">
            <Textarea
              value={placeholdersJson}
              onChange={(e) => setPlaceholdersJson(e.target.value)}
              placeholder={'{\n  "categories": [\n    { "category": "llms", "resources": [{ "rid": "llm_rid", "placeholders": [...] }] }\n  ]\n}'}
              className="h-[400px] font-mono text-xs bg-black/50 border-gray-800 text-gray-200 placeholder:text-gray-600 resize-none"
              spellCheck={false}
            />
          </TabsContent>
        </Tabs>

        {parseError && (
          <div className="flex items-start gap-2 p-3 rounded-md border border-red-800 bg-red-900/20 text-red-400 text-xs">
            <AlertCircle className="h-4 w-4 shrink-0 mt-0.5" />
            <span className="font-mono">{parseError}</span>
          </div>
        )}

        <DialogFooter>
          <Button variant="ghost" onClick={handleClose} disabled={isSubmitting}>
            Cancel
          </Button>
          <Button onClick={handleSubmit} disabled={isSubmitting || !draftYaml.trim()}>
            {isSubmitting ? 'Creating...' : 'Create Template'}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
};

export default CreateTemplateDialog;
