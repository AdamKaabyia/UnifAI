import React, { useState, useMemo } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Eye, Loader2 } from "lucide-react";
import { BuildingBlock } from "@/types/graph";
import { getCategoryDisplay } from "@/components/shared/helpers";
import ResourceDetailsModal from "./ResourceDetailsModal";
import { UmamiTrack } from '@/components/ui/umamitrack';
import { UmamiEvents } from '@/config/umamiEvents';
import { useTheme } from "@/contexts/ThemeContext";
import { deriveThemeColors } from "@/lib/colorUtils";

interface BuildingBlocksSidebarProps {
  buildingBlocks: BuildingBlock[];
  orchestrators: BuildingBlock[];
  conditions: BuildingBlock[];
  isLoading: boolean;
  onDragStart: (event: React.DragEvent, block: BuildingBlock) => void;
  usedElementIds?: Set<string>;
}

const BuildingBlocksSidebar: React.FC<BuildingBlocksSidebarProps> = ({
  buildingBlocks,
  orchestrators,
  conditions,
  isLoading,
  onDragStart,
  usedElementIds = new Set<string>(),
}) => {
  const [selectedElement, setSelectedElement] = useState<BuildingBlock | null>(null);
  const [isDetailsModalOpen, setIsDetailsModalOpen] = useState(false);
  const { primaryHex } = useTheme();

  const sortedBlocks = useMemo(
    () => [...buildingBlocks].sort((a, b) => a.label.localeCompare(b.label)),
    [buildingBlocks]
  );
  const sortedOrchestrators = useMemo(
    () => [...orchestrators].sort((a, b) => a.label.localeCompare(b.label)),
    [orchestrators]
  );
  const sortedConditions = useMemo(
    () => [...conditions].sort((a, b) => a.label.localeCompare(b.label)),
    [conditions]
  );

  const themeColors = useMemo(() => {
    const t = deriveThemeColors(primaryHex);
    return {
      iconBg: t.primary,
      conditionBg: t.conditionAccent,
      conditionCardBg: t.conditionCardBg,
      conditionCardBorder: t.conditionCardBorder,
    };
  }, [primaryHex]);

  const handleViewDetails = (block: BuildingBlock) => {
    setSelectedElement(block);
    setIsDetailsModalOpen(true);
  };

  const handleDragStart = (event: React.DragEvent, block: BuildingBlock) => {
    if (usedElementIds.has(block.id)) {
      event.preventDefault();
      return;
    }
    onDragStart(event, block);
  };

  const renderNodeCard = (block: BuildingBlock) => {
    const isUsed = usedElementIds.has(block.id);
    return (
      <Card
        key={block.id}
        className={`transition-colors ${
          isUsed
            ? 'bg-gray-900 border-gray-800 opacity-50 cursor-not-allowed'
            : 'bg-gray-800 border-gray-700 hover:border-gray-600 cursor-grab active:cursor-grabbing'
        }`}
        draggable={!isUsed}
        onDragStart={(event) => handleDragStart(event, block)}
      >
        <CardContent className="p-3">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2 flex-1 min-w-0">
              <div
                className="flex-shrink-0 flex items-center justify-center w-8 h-8 rounded-full text-xs font-semibold text-white"
                style={{ backgroundColor: themeColors.iconBg }}
              >
                {getCategoryDisplay(block.workspaceData?.category || "default").icon}
              </div>
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2">
                  <h4 className={`font-medium text-sm truncate ${isUsed ? 'text-gray-500' : 'text-white'}`}>
                    {block.label}
                  </h4>
                  {isUsed && (
                    <span className="flex-shrink-0 text-xs bg-gray-700 text-gray-300 px-1.5 py-0.5 rounded">
                      Used
                    </span>
                  )}
                </div>
                <p className="text-xs text-gray-400 truncate">
                  {block.workspaceData?.type || block.type}
                </p>
              </div>
            </div>
            {block.workspaceData && (
              <Button
                variant="ghost"
                size="sm"
                className="flex-shrink-0 h-8 w-8 p-0 text-gray-400 hover:text-white"
                onClick={() => handleViewDetails(block)}
                aria-label={`View details for ${block.label}`}
              >
                <Eye className="h-4 w-4" />
              </Button>
            )}
          </div>
        </CardContent>
      </Card>
    );
  };

  const renderConditionCard = (condition: BuildingBlock) => {
    const isUsed = usedElementIds.has(condition.id);
    return (
      <Card
        key={condition.id}
        className={`transition-colors ${
          isUsed
            ? 'bg-gray-900 border-gray-800 opacity-50 cursor-not-allowed'
            : 'cursor-grab active:cursor-grabbing'
        }`}
        style={{
          backgroundColor: isUsed ? undefined : themeColors.conditionCardBg,
          borderColor: isUsed ? undefined : themeColors.conditionCardBorder,
        }}
        draggable={!isUsed}
        onDragStart={(event) => handleDragStart(event, condition)}
      >
        <CardContent className="p-3">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2 flex-1 min-w-0">
              <div
                className="flex-shrink-0 flex items-center justify-center w-8 h-8 rounded-full text-xs font-semibold text-white"
                style={{ backgroundColor: themeColors.conditionBg }}
              >
                {getCategoryDisplay("conditions").icon}
              </div>
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2">
                  <h4 className={`font-medium text-sm truncate ${isUsed ? 'text-gray-500' : 'text-white'}`}>
                    {condition.label}
                  </h4>
                  {isUsed && (
                    <span className="flex-shrink-0 text-xs bg-gray-700 text-gray-300 px-1.5 py-0.5 rounded">
                      Used
                    </span>
                  )}
                </div>
                <p className="text-xs text-gray-400 truncate">
                  {condition.workspaceData?.type || condition.type}
                </p>
              </div>
            </div>
            {condition.workspaceData && (
              <Button
                variant="ghost"
                size="sm"
                className="flex-shrink-0 h-8 w-8 p-0 text-gray-400 hover:text-white"
                onClick={() => handleViewDetails(condition)}
                aria-label={`View details for ${condition.label}`}
              >
                <Eye className="h-4 w-4" />
              </Button>
            )}
          </div>
        </CardContent>
      </Card>
    );
  };

  return (
    <div className="w-[340px] h-full flex-shrink-0">
      <Card className="bg-background-card shadow-card border-gray-800 h-full flex flex-col">
        <CardHeader className="py-3 px-6 border-b border-gray-800">
          <CardTitle className="text-lg font-heading">Elements</CardTitle>
        </CardHeader>
        <CardContent className="p-4 flex-1 overflow-hidden flex flex-col">
          <div className="flex-1 min-h-0">
            <Tabs defaultValue="nodes" className="h-full flex flex-col">
              <TabsList className="grid w-full grid-cols-3 bg-gray-800 h-auto p-1">
                <TabsTrigger value="nodes" className="text-gray-300 data-[state=active]:text-white text-xs px-2 py-1.5">
                  Agents ({buildingBlocks.length})
                </TabsTrigger>
                <TabsTrigger value="orchestrators" className="text-gray-300 data-[state=active]:text-white text-xs px-2 py-1.5">
                  Orchestrators ({orchestrators.length})
                </TabsTrigger>
                <UmamiTrack event={UmamiEvents.AGENT_GRAPHS_CONDITIONS_BUTTON} includeUserData={false}>
                  <TabsTrigger value="conditions" className="text-gray-300 data-[state=active]:text-white text-xs px-2 py-1.5">
                    Conditions ({conditions.length})
                  </TabsTrigger>
                </UmamiTrack>
              </TabsList>

              <TabsContent value="nodes" className="mt-4">
                {isLoading ? (
                  <div className="flex items-center justify-center h-32">
                    <Loader2 className="h-8 w-8 animate-spin text-primary" />
                    <span className="ml-2 text-sm text-gray-400">Loading...</span>
                  </div>
                ) : buildingBlocks.length === 0 ? (
                  <div className="text-center py-8 text-gray-500 text-sm">No agents available</div>
                ) : (
                  <div className="space-y-2 overflow-y-auto" style={{ maxHeight: 'calc(100vh - 430px)' }}>
                    {sortedBlocks.map(renderNodeCard)}
                  </div>
                )}
              </TabsContent>

              <TabsContent value="orchestrators" className="mt-4">
                {isLoading ? (
                  <div className="flex items-center justify-center h-32">
                    <Loader2 className="h-8 w-8 animate-spin text-primary" />
                    <span className="ml-2 text-sm text-gray-400">Loading...</span>
                  </div>
                ) : orchestrators.length === 0 ? (
                  <div className="text-center py-8 text-gray-500 text-sm">No orchestrators available</div>
                ) : (
                  <div className="space-y-2 overflow-y-auto" style={{ maxHeight: 'calc(100vh - 430px)' }}>
                    {sortedOrchestrators.map(renderNodeCard)}
                  </div>
                )}
              </TabsContent>

              <TabsContent value="conditions" className="mt-4">
                {isLoading ? (
                  <div className="flex items-center justify-center h-32">
                    <Loader2 className="h-8 w-8 animate-spin text-primary" />
                    <span className="ml-2 text-sm text-gray-400">Loading...</span>
                  </div>
                ) : conditions.length === 0 ? (
                  <div className="text-center py-8 text-gray-500 text-sm">No conditions available</div>
                ) : (
                  <div className="space-y-2 overflow-y-auto" style={{ maxHeight: 'calc(100vh - 430px)' }}>
                    {sortedConditions.map(renderConditionCard)}
                  </div>
                )}
              </TabsContent>
            </Tabs>
          </div>

          {!isLoading && (
            <div className="mt-4 p-4 bg-gray-900 rounded-lg border border-gray-700 flex-shrink-0">
              <h4 className="font-medium text-white mb-2">How to use:</h4>
              <div className="text-xs text-gray-400 space-y-1">
                <p>• Drag elements from sidebar to canvas</p>
                <p>• Click a node, then click another to connect</p>
                <p>• Drag conditions onto nodes for branching</p>
                <p>• Press Delete or ESC to remove / cancel</p>
                <p>• Always start with User Input node</p>
                <p>• End workflow with Final Answer node</p>
              </div>
            </div>
          )}
        </CardContent>
      </Card>

      <ResourceDetailsModal
        isOpen={isDetailsModalOpen}
        onClose={() => setIsDetailsModalOpen(false)}
        element={selectedElement}
      />
    </div>
  );
};

export default BuildingBlocksSidebar;
