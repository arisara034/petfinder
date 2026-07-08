const express = require("express")
const mongoose = require("mongoose")
const multer = require("multer")
const cors = require("cors")
const fs = require("fs")
const { createCanvas, loadImage } = require("canvas")

const app = express()

app.use(cors())
app.use(express.json())
app.use(express.urlencoded({extended:true}))

app.use(express.static("public"))
app.use("/uploads",express.static("uploads"))
app.use("/posters",express.static("posters"))

mongoose.connect(process.env.MONGO_URI)
.then(()=>console.log("MongoDB connected"))

const Pet = require("./models/Pet")

// upload config
const storage = multer.diskStorage({
destination:(req,file,cb)=>{
cb(null,"uploads/")
},
filename:(req,file,cb)=>{
cb(null,Date.now()+"-"+file.originalname)
}
})

const upload = multer({storage})

// AI Poster
async function createPoster(pet){

const canvas = createCanvas(800,1000)
const ctx = canvas.getContext("2d")

ctx.fillStyle="#fff"
ctx.fillRect(0,0,800,1000)

ctx.fillStyle="red"
ctx.font="bold 60px Arial"
ctx.fillText("LOST PET",230,120)

ctx.fillStyle="#000"
ctx.font="40px Arial"

ctx.fillText("ชื่อ: "+pet.name,100,300)
ctx.fillText("ประเภท: "+pet.type,100,370)
ctx.fillText("สถานที่: "+pet.location,100,440)

let imgPath

if(pet.image){
imgPath="uploads/"+pet.image
}else{
imgPath="public/icons/dog.png"
}

const img = await loadImage(imgPath)

ctx.drawImage(img,200,500,400,300)

const posterPath = "posters/"+pet._id+".png"

fs.writeFileSync(posterPath,canvas.toBuffer())

return posterPath
}

// GET pets
app.get("/pets",async(req,res)=>{

const pets = await Pet.find().sort({createdAt:-1})

res.json(pets)

})

// ADD pet
app.post("/pets",upload.single("image"),async(req,res)=>{

const pet = new Pet({

name:req.body.name,
type:req.body.type,
location:req.body.location,
lat:req.body.lat,
lng:req.body.lng,
image:req.file ? req.file.filename : null

})

await pet.save()

const poster = await createPoster(pet)

pet.poster = poster

await pet.save()

res.json(pet)

})

// DELETE
app.delete("/pets/:id",async(req,res)=>{

await Pet.findByIdAndDelete(req.params.id)

res.json({message:"deleted"})

})

// PORT สำหรับ deploy
const PORT = process.env.PORT || 3000

app.listen(PORT,()=>{
console.log("Server running")
})