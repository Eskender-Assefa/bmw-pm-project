'use client';
import * as Dialog from '@radix-ui/react-dialog';
import { X } from 'lucide-react';
import { useId, type ReactNode } from 'react';
import { cn } from '@/lib/utils';
export function Modal({open,onClose,title,description,children,wide=false,drawer=false}:{open:boolean;onClose:()=>void;title:string;description?:string;children:ReactNode;wide?:boolean;drawer?:boolean}){
 const descriptionId=useId();
 return <Dialog.Root open={open} onOpenChange={v=>{if(!v)onClose();}}><Dialog.Portal><Dialog.Overlay className="dialog-overlay"/><Dialog.Content className={cn('dialog-content',wide&&'dialog-wide',drawer&&'dialog-drawer')} aria-describedby={description?descriptionId:undefined}>
 <div className="dialog-heading"><div><Dialog.Title>{title}</Dialog.Title>{description&&<Dialog.Description id={descriptionId}>{description}</Dialog.Description>}</div><Dialog.Close className="icon-button" aria-label="Close dialog"><X size={20}/></Dialog.Close></div>{children}
 </Dialog.Content></Dialog.Portal></Dialog.Root>;
}
