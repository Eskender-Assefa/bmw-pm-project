// Deterministic SDK contract double. Live model rendering is verified separately.
export function installViewerDouble(){
  window.viewerOperations=[];
  window.Sketchfab=class {
    constructor(version,frame){this.frame=frame;}
    init(id,options){
      this.frame.srcdoc='<body style="background:#dfeaf4;color:#315877;font:18px sans-serif;display:grid;place-items:center;height:90vh">Hosted viewer test double</body>';
      const matrix=[1,0,0,0,0,1,0,0,0,0,1,0,0,0,0,1];
      const materials=['Car_Body','Door_Panel','Glass','Interior','Seats','SteeringWheel','Lights'].map((name,i)=>({id:name,name,stateSetID:i,channels:{AlbedoPBR:{enable:true,color:[.3,.3,.3]},EmitColor:{enable:true,color:[0,0,0]},Opacity:{enable:false,factor:1}}}));
      let serial=0,camera={position:[0,.65,1.2],target:[0,-.45,.93]};const record=(op,data)=>window.viewerOperations.push({op,data:structuredClone(data)});
      const api={
        start(){},addEventListener(name,cb){if(name==='viewerready')setTimeout(cb,5);},
        getNodeMap(cb){cb(null,{160:{instanceID:160,name:'Seats_9',type:'MatrixTransform',localMatrix:Object.fromEntries(matrix.map((v,i)=>[i,v]))}});},
        getMaterialList(cb){cb(null,structuredClone(materials));},
        createMaterial(m,cb){cb(null,{...m,id:'demo-'+(++serial),stateSetID:100+serial});},
        setMaterial(m,cb){record('material',m);cb?.(null);},
        setMatrix(id,m,cb){record('matrix',{id,m});cb?.(null);},
        createDecal(data,cb){record('decal',data);cb(null,{id:'decal-'+(++serial)});},
        destroyDecal(id,options,cb){record('destroy',id);cb?.(null);},
        setFov(angle,cb){record('fov',angle);cb?.(null,angle);},
        setCameraLookAt(position,target,duration,cb){camera={position,target};record('camera',camera);cb?.(null);},
        getCameraLookAt(cb){cb(null,camera);},
        getWorldToScreenCoordinates(position,cb){record('project',position);cb({canvasCoord:[250-position[0]*180,220-(position[2]-1)*180],glCoord:[0,0,0]});},
      };options.success(api);
    }
  };
}
