// Proposed functions.exec orchestration; definitions only, no top-level effects.
function exactUTF8Base64(s) {
  const bytes=[];
  for (const ch of s) {
    const p=ch.codePointAt(0);
    if(p>=0xD800&&p<=0xDFFF) throw Error("unpaired surrogate; preserve original toolreply");
    if(p<128)bytes.push(p);
    else if(p<2048)bytes.push(192|(p>>6),128|(p&63));
    else if(p<65536)bytes.push(224|(p>>12),128|((p>>6)&63),128|(p&63));
    else bytes.push(240|(p>>18),128|((p>>12)&63),128|((p>>6)&63),128|(p&63));
  }
  const a="ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/";
  const blocks=[];let block="";
  for(let i=0;i<bytes.length;i+=3){
    const n=(bytes[i]<<16)|((bytes[i+1]??0)<<8)|(bytes[i+2]??0);
    block+=a[(n>>>18)&63]+a[(n>>>12)&63]+(i+1<bytes.length?a[(n>>>6)&63]:"=")+(i+2<bytes.length?a[n&63]:"=");
    if(block.length>=16384){blocks.push(block);block="";}
  }
  blocks.push(block);return blocks.join("");
}
async function boundedReadback(plan,label,planPath) {
  const B="/dev/shm/github-product32-attachment-award";
  const D=B+"/streaming-body";
  const proof=[];
  for(let i=0;i<plan.length;i++){
    const index=String(i).padStart(3,"0"),x=plan[i];
    const pre=await tools.exec_command({cmd:"python "+B+"/stream_remote_readback.py preflight --plan "+planPath+" --index "+i+" --label "+label+" --receipt "+D+"/"+label+"/preflight/"+index+".json --reserve-bytes 2097152",max_output_tokens:1000,yield_time_ms:30000});
    if(pre.exit_code!==0)throw Error("STOP bytebudget/canonical preflight: "+JSON.stringify(pre));
    const r=await tools.mcp__codex_apps__github_fetch_blob({repository_full_name:"guarani-ux/"+x.repo,blob_sha:x.git_sha1});
    store("p32stream-current-actual-reply",{index:i,request:x,reply:r});
    if(r.isError||typeof r.structuredContent?.content!=="string"){
      await tools.apply_patch("*** Begin Patch\n*** Add File: "+D+"/"+label+"/READ_ERROR_"+index+".json\n+"+JSON.stringify({index:i,request:x,reply:r},null,2).split("\n").join("\n+")+"\n*** End Patch");
      throw Error("STOP actualread error, no retry");
    }
    const envelope=JSON.stringify({index:i,actual_value_base64:exactUTF8Base64(r.structuredContent.content)});
    if(envelope.length+1>2097152)throw Error("STOP inputbudget; preserve actual toolreply in store");
    const input=D+"/incoming/"+label+"-"+index+".json";
    await tools.apply_patch("*** Begin Patch\n*** Add File: "+input+"\n+"+envelope+"\n*** End Patch");
    const receipt=D+"/"+label+"/values/"+index+".json";
    const check=await tools.exec_command({cmd:"python "+B+"/stream_remote_readback.py value --plan "+planPath+" --index "+i+" --input "+input+" --label "+label+" --receipt "+receipt,max_output_tokens:1000,yield_time_ms:30000});
    proof.push({index:i,repo:x.repo,path:x.path,receipt,actual_helper_reply:check});
    store("p32stream-"+label,proof);
    if(check.exit_code!==0)throw Error("STOP preserve actualvalue/failure: "+JSON.stringify(check));
    if(i%8===0)notify({phase:label,full_actual_values_verified:i+1,total:plan.length});
  }
  return proof;
}

