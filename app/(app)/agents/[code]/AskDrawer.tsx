"use client";

import { MessageSquare } from "lucide-react";
import { useState } from "react";

import Conversation from "./Conversation";
import { Button } from "@/components/ui/button";
import {
  Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle, SheetTrigger,
} from "@/components/ui/sheet";

/* The conversation used to sit in a column beside the tool list, which meant the
 * page had two things competing for the reader's attention and the transcript
 * was stuck in a 24rem box. It is a side activity, so it belongs in a drawer:
 * the table gets the full width, and the conversation gets the full height.
 */
export default function AskDrawer({
  code, name, title, examples, signedIn,
}: {
  code: string;
  name: string;
  title: string;
  examples: string[];
  signedIn: boolean;
}) {
  const [open, setOpen] = useState(false);

  return (
    <Sheet open={open} onOpenChange={setOpen}>
      <SheetTrigger asChild>
        <Button variant="outline" size="sm" className="gap-1.5">
          <MessageSquare className="size-3.5" />
          Ask {name}
        </Button>
      </SheetTrigger>
      <SheetContent
        side="right"
        className="flex w-full flex-col gap-0 p-0 sm:max-w-xl"
      >
        <SheetHeader className="border-b px-5 py-4">
          <SheetTitle className="text-base">Ask {name}</SheetTitle>
          <SheetDescription>
            {title}. Same tools as when working inside the team.
          </SheetDescription>
        </SheetHeader>
        <Conversation
          code={code}
          name={name}
          examples={examples}
          signedIn={signedIn}
        />
      </SheetContent>
    </Sheet>
  );
}
